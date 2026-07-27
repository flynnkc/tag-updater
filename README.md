# Tag Updater

A script to update tag defaults in OCI

## Prerequisites

- An OCI Functions development environment (local, cloud shell, OCI code editor)
- A container environment (Docker, Podman, etc.)
- A [Dynamic Group](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingdynamicgroups.htm) with rules to include the Function in the group membership
- For OKE, a service account configured for OCI workload identity, or a node instance principal
- [Defined Tags](https://docs.oracle.com/en-us/iaas/Content/Tagging/Tasks/managingtagsandtagnamespaces.htm#workdefined) to update

## Deployment

### Entrypoints

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

### Policies

```text
Allow dynamic-group tag_update_dg to manage tag-defaults in tenancy
Allow dynamic-group tag_update_dg to use tag-namespaces in tenancy
Allow any-user to manage functions-family in tenancy where all {request.principal.type='resourceschedule',request.principal.id='ocid1.resourceschedule...'}
```

### Environment Variables

- TAG_NAMESPACE

    The [tag namespace](https://docs.oracle.com/en-us/iaas/Content/Tagging/Tasks/managingtagsandtagnamespaces.htm#workdefined) to be updated

- TAG_KEY

    The [tag key](https://docs.oracle.com/en-us/iaas/Content/Tagging/Tasks/managingtagsandtagnamespaces.htm#workdefined) to be updated (must be in selected namespace)

- COMPARTMENTS

    Comma delimited list of compartments to update

- LOG_LEVEL

    Log level for Function logs [CRITICAL, ERROR, WARNING, INFO, DEBUG]

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

    Optional tenancy OCID override. This is most useful for OKE workload
    identity, where the signer may not expose a tenancy OCID directly.

### OKE container image

Build and push the image to the registry used by your OKE cluster:

```sh
docker build -t <registry>/<repo>/tag-updater:<tag> .
docker push <registry>/<repo>/tag-updater:<tag>
```

For OKE workload identity, set:

```text
OCI_SIGNER=WORKLOAD_IDENTITY
OCI_RESOURCE_PRINCIPAL_REGION=<oci-region>
OCI_TENANCY_ID=<tenancy-ocid>
```

For instance principals on a compute host or OKE node, set:

```text
OCI_SIGNER=INSTANCE_PRINCIPAL
```
