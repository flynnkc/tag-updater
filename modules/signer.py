#!/usr/python3.11

import logging

from os import getenv
from oci import Signer
from oci.config import from_file, get_config_value_or_default, DEFAULT_LOCATION, DEFAULT_PROFILE
from oci.auth.signers import get_resource_principals_signer

log = logging.getLogger(__name__)

def create_signer() -> tuple[dict, Signer]:
    log.debug('Creating Signer')
        
    signer = get_resource_principals_signer()
    cfg = {
        'region': signer.region,
        'tenancy': signer.tenancy_id
           }
    
    log.debug(f'Signer: {signer}\nConfig: {cfg}')
    
    return cfg, signer