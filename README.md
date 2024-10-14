# Tag Updater

A script to update tag defaults in OCI

## Prerequisites

- An OCI Functions development environment (local, cloud shell, OCI code editor)
- A container environment (Docker, Podman, etc.)
- A [Dynamic Group](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingdynamicgroups.htm) with rules to include the Function in the group membership
- [Defined Tags](https://docs.oracle.com/en-us/iaas/Content/Tagging/Tasks/managingtagsandtagnamespaces.htm#workdefined) to update

## Deployment

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
