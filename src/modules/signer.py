#!/usr/bin/python3.11

import logging
import os
from typing import Any

from oci.auth.signers import InstancePrincipalsSecurityTokenSigner
from oci.auth.signers import get_oke_workload_identity_resource_principal_signer
from oci.auth.signers import get_resource_principals_signer

log = logging.getLogger(__name__)

ENV_AUTH_TYPE = 'OCI_SIGNER'
ENV_RESOURCE_PRINCIPAL_VERSION = 'OCI_RESOURCE_PRINCIPAL_VERSION'
ENV_KUBERNETES_SERVICE_HOST = 'KUBERNETES_SERVICE_HOST'
ENV_REGION = 'OCI_RESOURCE_PRINCIPAL_REGION'
ENV_TENANCY_ID = 'OCI_TENANCY_ID'

AUTH_AUTO = 'AUTO'
AUTH_RESOURCE_PRINCIPAL = 'RESOURCE_PRINCIPAL'
AUTH_INSTANCE_PRINCIPAL = 'INSTANCE_PRINCIPAL'
AUTH_WORKLOAD_IDENTITY = 'WORKLOAD_IDENTITY'
_AUTH_TYPES = {
    AUTH_AUTO,
    AUTH_RESOURCE_PRINCIPAL,
    AUTH_INSTANCE_PRINCIPAL,
    AUTH_WORKLOAD_IDENTITY,
}


def create_signer(auth_type: str | None = None) -> tuple[dict[str, str], Any]:
    signer_type = _resolve_auth_type(auth_type)
    log.debug(f'Creating OCI {signer_type} signer')

    if signer_type == AUTH_INSTANCE_PRINCIPAL:
        signer = InstancePrincipalsSecurityTokenSigner()
    elif signer_type == AUTH_WORKLOAD_IDENTITY:
        signer = get_oke_workload_identity_resource_principal_signer()
    else:
        signer = get_resource_principals_signer()

    cfg: dict[str, str] = {
        'region': _get_region(signer),
        'tenancy': _get_tenancy_id(signer),
    }

    log.debug(f'Created OCI {signer_type} signer')

    return cfg, signer


def _resolve_auth_type(auth_type: str | None = None) -> str:
    configured = (
        auth_type
        or os.getenv(ENV_AUTH_TYPE)
        or AUTH_AUTO
    ).strip().upper()
    if configured not in _AUTH_TYPES:
        raise ValueError(
            f'Invalid OCI auth type: {configured}. Expected one of '
            f'{", ".join(sorted(_AUTH_TYPES))}'
        )

    if configured != AUTH_AUTO:
        return configured

    if os.getenv(ENV_RESOURCE_PRINCIPAL_VERSION):
        return AUTH_RESOURCE_PRINCIPAL
    if os.getenv(ENV_KUBERNETES_SERVICE_HOST):
        return AUTH_WORKLOAD_IDENTITY

    # Preserve the historical default for OCI Functions.
    return AUTH_RESOURCE_PRINCIPAL


def _get_region(signer: Any) -> str:
    region = getattr(signer, 'region', None) or os.getenv(ENV_REGION)
    if not region:
        raise ValueError(
            'Unable to determine OCI region from signer. Set '
            f'{ENV_REGION} or choose a signer that exposes region.'
        )

    return region


def _get_tenancy_id(signer: Any) -> str:
    tenancy_id = (
        getattr(signer, 'tenancy_id', None)
        or os.getenv(ENV_TENANCY_ID)
        or _get_tenancy_from_security_token(signer)
    )
    if not tenancy_id:
        raise ValueError(
            'Unable to determine OCI tenancy OCID from signer. Set '
            f'{ENV_TENANCY_ID}.'
        )

    return tenancy_id


def _get_tenancy_from_security_token(signer: Any) -> str | None:
    token = getattr(signer, 'security_token', None)
    if not token or not hasattr(token, 'get_jwt'):
        return None

    jwt = token.get_jwt()
    for claim in ('tenancy_id', 'tenant_id', 'res_tenant', 'oci_tenancy_id'):
        if jwt.get(claim):
            return jwt[claim]

    return None
