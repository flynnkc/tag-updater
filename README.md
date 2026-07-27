# Tag Updater

A script to update tag defaults in OCI

## Prerequisites

- [Defined Tags](https://docs.oracle.com/en-us/iaas/Content/Tagging/Tasks/managingtagsandtagnamespaces.htm#workdefined) to update

For OCI Functions:

- An OCI Functions development environment (local, cloud shell, OCI code editor)
- A [Dynamic Group](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingdynamicgroups.htm) with rules to include the Function in the group membership

For OKE:

- A container environment, such as Docker or Podman
- Access to an OKE cluster
- A service account configured for OCI workload identity, or a node instance principal

## Entrypoints

The core update behavior lives in `modules/app.py`.

- OCI Functions uses `func.py` through the existing `func.yaml` entrypoint:

    ```text
    /python/bin/fdk /function/func.py handler
    ```

- OKE or another container runtime uses `container.py` through the `Dockerfile`
  entrypoint:

    ```text
    python /app/container.py
    ```

The container entrypoint runs once and exits `0` for successful updates or `1`
for validation/update failures, making it suitable for Kubernetes Jobs or
CronJobs.

## Environment Variables

#### Required

- TAG_NAMESPACE

    The [tag namespace](https://docs.oracle.com/en-us/iaas/Content/Tagging/Tasks/managingtagsandtagnamespaces.htm#workdefined)
    to be updated.

- TAG_KEY

    The [tag key](https://docs.oracle.com/en-us/iaas/Content/Tagging/Tasks/managingtagsandtagnamespaces.htm#workdefined)
    to be updated. The key must be in the selected namespace.

#### Optional

- COMPARTMENTS

    Comma-delimited list of compartment OCIDs to update. When omitted, the
    tenancy root compartment is used.

- LOG_LEVEL

    Log level for Function or container logs. Defaults to `INFO`.

    Supported values:

    - `CRITICAL`
    - `ERROR`
    - `WARNING`
    - `INFO`
    - `DEBUG`

- DAYS

    Number of days to add to the current date when setting the tag default
    value. Defaults to `90`.

- OCI_SIGNER

    Optional OCI signer selection. Defaults to `AUTO`.

    Supported values:

    - `AUTO`
    - `RESOURCE_PRINCIPAL`
    - `INSTANCE_PRINCIPAL`
    - `WORKLOAD_IDENTITY`

    `AUTO` preserves the OCI Functions resource-principal flow when Functions
    resource principal variables are present, uses OKE workload identity when
    Kubernetes service variables are present, and otherwise falls back to the
    original resource-principal behavior.

- OCI_TENANCY_ID

    Tenancy OCID override. Optional when the signer exposes the tenancy OCID or
    the generated security token includes a tenancy claim. Required when tenancy
    cannot be derived from the selected signer.

#### Runtime-provided

These are normally provided by OCI Functions, Kubernetes, or the OCI SDK signer
flow rather than configured manually for every deployment.

- OCI_RESOURCE_PRINCIPAL_VERSION

    Provided by OCI Functions resource-principal environments. When
    `OCI_SIGNER=AUTO`, its presence selects `RESOURCE_PRINCIPAL`.

- KUBERNETES_SERVICE_HOST

    Provided by Kubernetes pods. When `OCI_SIGNER=AUTO`, its presence selects
    `WORKLOAD_IDENTITY` if resource-principal variables are not present.

- OCI_RESOURCE_PRINCIPAL_REGION

    OCI region used when the signer does not expose region directly. For OKE
    workload identity deployments, set this to the target OCI region.

## Deployment

### OCI Functions

Use the existing `func.yaml` to build and deploy as an OCI Function.

Function IAM policies:

```text
Allow dynamic-group tag_update_dg to manage tag-defaults in tenancy
Allow dynamic-group tag_update_dg to use tag-namespaces in tenancy
Allow any-user to manage functions-family in tenancy where all {request.principal.type='resourceschedule',request.principal.id='ocid1.resourceschedule...'}
```

Function configuration should include at least:

```text
TAG_NAMESPACE=<tag-namespace>
TAG_KEY=<tag-key>
```

Optional Function configuration:

```text
COMPARTMENTS=<compartment-ocid-1>,<compartment-ocid-2>
DAYS=90
LOG_LEVEL=INFO
OCI_SIGNER=AUTO
```

`OCI_SIGNER=AUTO` preserves the original OCI Functions resource-principal
behavior when resource-principal environment variables are present.

### OKE CronJob

Use the `Dockerfile` and `container.py` entrypoint to run this project as a
Kubernetes CronJob on OKE.

#### Build and push the image

Build the container image:

```sh
docker build -t tag-updater:0.1.13 .
```

Tag and push the image to
[OCI Container Registry](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrypushingimagesusingthedockercli.htm):

```sh
export OCIR_REGION=<region-key>
export OCIR_NAMESPACE=<tenancy-namespace>
export OCIR_REPOSITORY=<repo-name>
export IMAGE_TAG=0.1.13

docker tag tag-updater:${IMAGE_TAG} \
  ${OCIR_REGION}.ocir.io/${OCIR_NAMESPACE}/${OCIR_REPOSITORY}/tag-updater:${IMAGE_TAG}

docker push \
  ${OCIR_REGION}.ocir.io/${OCIR_NAMESPACE}/${OCIR_REPOSITORY}/tag-updater:${IMAGE_TAG}
```

If the OCIR repository is private, create an image pull secret in the target
namespace. See Oracle's documentation for
[pulling images from OCIR during Kubernetes deployment](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrypullingimagesfromocir.htm).

```sh
kubectl create namespace tag-updater

kubectl create secret docker-registry ocir-pull-secret \
  --namespace tag-updater \
  --docker-server=${OCIR_REGION}.ocir.io \
  --docker-username='<tenancy-namespace>/<username>' \
  --docker-password='<auth-token>' \
  --docker-email='<email-address>'
```

For OKE workload identity, use an enhanced OKE cluster and grant the workload
identity access to OCI resources. Oracle's
[workload identity documentation](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contenggrantingworkloadaccesstoresources.htm)
describes the model. The workload identity is the combination of cluster,
namespace, and service account.

Example IAM policy:

```text
Allow any-user to manage tag-defaults in tenancy where all {
  request.principal.type = 'workload',
  request.principal.namespace = 'tag-updater',
  request.principal.service_account = 'tag-updater',
  request.principal.cluster_id = '<cluster-ocid>'
}
Allow any-user to use tag-namespaces in tenancy where all {
  request.principal.type = 'workload',
  request.principal.namespace = 'tag-updater',
  request.principal.service_account = 'tag-updater',
  request.principal.cluster_id = '<cluster-ocid>'
}
```

#### Deploy the CronJob

Save the following templates and replace the placeholder values before applying
them.

Namespace and service account:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tag-updater
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tag-updater
  namespace: tag-updater
```

Configuration:

Remove `COMPARTMENTS` to update the tenancy root compartment.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tag-updater-config
  namespace: tag-updater
data:
  TAG_NAMESPACE: "<tag-namespace>"
  TAG_KEY: "<tag-key>"
  COMPARTMENTS: "<compartment-ocid-1>,<compartment-ocid-2>"
  DAYS: "90"
  LOG_LEVEL: "INFO"
  OCI_SIGNER: "WORKLOAD_IDENTITY"
  OCI_RESOURCE_PRINCIPAL_REGION: "<oci-region>"
  OCI_TENANCY_ID: "<tenancy-ocid>"
```

CronJob:

Remove `imagePullSecrets` if the image is public or your cluster can already
pull it without a Kubernetes registry secret.

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: tag-updater
  namespace: tag-updater
spec:
  schedule: "0 6 * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 1
      template:
        spec:
          serviceAccountName: tag-updater
          automountServiceAccountToken: true
          restartPolicy: Never
          imagePullSecrets:
            - name: ocir-pull-secret
          containers:
            - name: tag-updater
              image: <region-key>.ocir.io/<tenancy-namespace>/<repo-name>/tag-updater:0.1.13
              imagePullPolicy: IfNotPresent
              envFrom:
                - configMapRef:
                    name: tag-updater-config
```

Apply the templates:

```sh
kubectl apply -f tag-updater-namespace.yaml
kubectl apply -f tag-updater-config.yaml
kubectl apply -f tag-updater-cronjob.yaml
```

Check the CronJob and its latest run:

```sh
kubectl get cronjob tag-updater -n tag-updater
kubectl get jobs -n tag-updater
kubectl logs -n tag-updater job/<job-name>
```

For instance principals on a compute host or OKE node, use the same templates
and change the signer:

```text
OCI_SIGNER=INSTANCE_PRINCIPAL
```
