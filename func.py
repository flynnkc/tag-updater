#!/usr/bin/python3.11

import io
import logging
import os

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
    

def handler(ctx, data: io.BytesIO = None):

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

    config, signer = create_signer()
    log.debug(f'Config: {config}\n\tSigner: {signer}')

    # Compartments needs to be a list of OCIDs whether provided or not
    compartments = os.getenv(ENV_COMPARTMENTS)     # Comma delimited string
    compartments = compartments.split(',') if compartments else [config['tenancy']]

    log.info(f'Updating tag default {namespace}.{key} in compartment(s) '
             f'{compartments}')

    tc = TagUpdater(config, compartments, signer=signer)
    tc.update_tags(namespace, key)

    log.info(f'Updates complete on compartments {", ".join(compartments)}')

    return response.Response(ctx)
