#!/usr/bin/python3.11

import io
import logging
import os
from typing import Any

from fdk import response
from modules import create_signer
from modules import TagUpdater

ENV_NAMESPACE = 'TAG_NAMESPACE'
ENV_KEY = 'TAG_KEY'
ENV_COMPARTMENTS = 'COMPARTMENTS'
ENV_LOGLVL = 'LOG_LEVEL'
_TREE = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}
    

def handler(ctx: Any, data: io.BytesIO | None = None) -> Any:

    try:
        level = _TREE[os.getenv(ENV_LOGLVL, 'INFO').upper()]
        logging.basicConfig(level=level, force=True)
    except KeyError:
        logging.basicConfig(level=logging.INFO, force=True)
        logging.error(f'Invalid log level selected: {os.getenv(ENV_LOGLVL)}'
                ' -- Reverting to level INFO')

    log = logging.getLogger(__name__)

    log.debug(f'Log level: {os.getenv(ENV_LOGLVL, "INFO")} -- '
              f'{log.getEffectiveLevel()}')

    namespace = os.getenv(ENV_NAMESPACE)
    key = os.getenv(ENV_KEY)

    if not namespace or not key:
        missing = [name for name, value in {
            ENV_NAMESPACE: namespace,
            ENV_KEY: key,
        }.items() if not value]
        return response.Response(
            ctx,
            status_code=400,
            response_data=f'Missing required environment variable(s): {", ".join(missing)}',
            headers={'Content-Type': 'text/plain'},
        )

    config, signer = create_signer()
    log.debug('Created OCI resource-principal signer')

    # Compartments needs to be a list of OCIDs whether provided or not
    configured_compartments = os.getenv(ENV_COMPARTMENTS)
    compartments = (
        [compartment.strip() for compartment in configured_compartments.split(',')
         if compartment.strip()]
        if configured_compartments
        else []
    )
    if not compartments:
        compartments = [config['tenancy']]

    log.info(f'Updating tag default {namespace}.{key} in compartment(s) '
             f'{compartments}')

    tc = TagUpdater(config, compartments, signer=signer)
    status_code, response_data = tc.update_tags(namespace, key)

    log.info(f'Updates complete on compartments {", ".join(compartments)}')

    return response.Response(ctx,
                             status_code=status_code,
                             response_data=response_data,
                             headers={'Content-Type': 'text/plain'})
