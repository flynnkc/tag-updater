#!/usr/bin/python3.11

import logging
import os

from oci.signer import Signer

from modules import create_signer
from modules import TagUpdater

ENV_NAMESPACE = 'TAG_NAMESPACE'
ENV_KEY = 'TAG_KEY'
ENV_COMPARTMENTS = 'COMPARTMENTS'
ENV_LOGLVL = 'LOG_LEVEL'
ENV_OCI_LOG_ID = 'OCI_LOG_ID'
ENV_OCI_LOG_REGION = 'OCI_LOG_REGION'

_TREE = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}


def configure_logging(config: dict[str, str] | None = None,
                      signer: Signer | None = None) -> None:
    """Configure console logging and, optionally, OCI custom-log delivery."""
    try:
        level = _TREE[os.getenv(ENV_LOGLVL, 'INFO').upper()]
        logging.basicConfig(level=level, force=True)
    except KeyError:
        logging.basicConfig(level=logging.INFO, force=True)
        logging.error(f'Invalid log level selected: {os.getenv(ENV_LOGLVL)}'
                      ' -- Reverting to level INFO')

    log_id = os.getenv(ENV_OCI_LOG_ID)
    if not log_id:
        return

    try:
        from oci_log_handler import OciLoggingHandler

        log_config: dict[str, str] = dict(config) if config else {}
        signer_region: str | None = getattr(signer, 'region', None)
        if not isinstance(signer_region, str):
            signer_region = None
        log_region = (
            os.getenv(ENV_OCI_LOG_REGION)
            or signer_region
            or log_config.get('region')
        )
        if log_region:
            log_config['region'] = log_region
        handler = OciLoggingHandler(
            log_id,
            config=log_config,
            signer=signer,
            source='tag-updater',
        )
        logging.getLogger().addHandler(handler)
    except Exception:
        logging.getLogger(__name__).exception(
            'Unable to configure OCI custom-log transport; continuing with '
            'console logging only'
        )


def flush_logging() -> None:
    """Flush handlers at the end of an invocation, including OCI batches."""
    for handler in logging.getLogger().handlers:
        handler.flush()


def run_update() -> tuple[int, str]:
    namespace = os.getenv(ENV_NAMESPACE)
    key = os.getenv(ENV_KEY)

    if not namespace or not key:
        missing = [name for name, value in {
            ENV_NAMESPACE: namespace,
            ENV_KEY: key,
        }.items() if not value]
        return (
            400,
            f'Missing required environment variable(s): {", ".join(missing)}',
        )

    config, signer = create_signer()
    configure_logging(config, signer)
    log = logging.getLogger(__name__)

    try:
        log.debug(f'Log level: {os.getenv(ENV_LOGLVL, "INFO")} -- '
                  f'{log.getEffectiveLevel()}')

        # Compartments needs to be a list of OCIDs whether provided or not.
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

        return status_code, response_data
    finally:
        flush_logging()
