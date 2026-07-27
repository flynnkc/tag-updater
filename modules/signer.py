#!/usr/python3.11

import logging

from oci import Signer
from oci.auth.signers import get_resource_principals_signer

log = logging.getLogger(__name__)

def create_signer() -> tuple[dict[str, str], Signer]:
    log.debug('Creating Signer')
        
    signer = get_resource_principals_signer()
    cfg: dict[str, str] = {
        'region': signer.region,
        'tenancy': signer.tenancy_id
           }
    
    log.debug('Created OCI resource-principal signer')
    
    return cfg, signer
