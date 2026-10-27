#!/usr/bin/python3.11

import logging
import os
from time import monotonic

from oci.signer import Signer

from modules import create_signer
from modules import TagUpdater

ENV_NAMESPACE = 'TAG_NAMESPACE'
ENV_KEY = 'TAG_KEY'
ENV_COMPARTMENTS = 'COMPARTMENTS'
ENV_LOGLVL = 'LOG_LEVEL'
ENV_OCI_LOG_ID = 'OCI_LOG_ID'
ENV_OCI_LOG_REGION = 'OCI_LOG_REGION'

LOG_TREE = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}


def configure_oci_logging(config: dict[str, str] | None = None,
                          signer: Signer | None = None) -> None:
    """Add optional OCI custom-log delivery to the configured console logging."""
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
        logging.getLogger(__name__).info(
            'OCI custom-log delivery enabled: log=%s region=%s',
            log_id, log_region,
        )
    except Exception:
        logging.getLogger(__name__).exception(
            'Unable to configure OCI custom-log transport; continuing with '
            'console logging only'
        )


def configure_console_logging() -> None:
    """Enable console logs before validation and signer initialization."""
    try:
        level = LOG_TREE[os.getenv(ENV_LOGLVL, 'INFO').upper()]
        logging.basicConfig(level=level, force=True)
    except KeyError:
        logging.basicConfig(level=logging.INFO, force=True)
        logging.error('Invalid log level selected: %s -- Reverting to level INFO',
                      os.getenv(ENV_LOGLVL))


def flush_logging() -> None:
    """Flush handlers at the end of an invocation, including OCI batches."""
    for handler in logging.getLogger().handlers:
        handler.flush()


def run_update() -> tuple[int, str]:
    started = monotonic()
    configure_console_logging()
    log = logging.getLogger(__name__)
    namespace = os.getenv(ENV_NAMESPACE)
    key = os.getenv(ENV_KEY)

    if not namespace or not key:
        missing = [name for name, value in {
            ENV_NAMESPACE: namespace,
            ENV_KEY: key,
        }.items() if not value]
        message = f'Missing required environment variable(s): {", ".join(missing)}'
        log.error(message)
        return 400, message

    try:
        log.info('Starting tag default update for %s.%s', namespace, key)
        config, signer = create_signer()
        configure_oci_logging(config, signer)

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
            log.info('COMPARTMENTS not configured; using tenancy root compartment')

        log.info('Updating tag default %s.%s in %d compartment(s): %s; '
                 'identity region=%s', namespace, key, len(compartments),
                 ', '.join(compartments), config.get('region'))

        tc = TagUpdater(config, compartments, signer=signer)
        status_code, response_data = tc.update_tags(namespace, key)

        log.log(logging.INFO if 200 <= status_code < 300 else logging.ERROR,
                'Tag default update finished: status=%d duration=%.2fs result=%s',
                status_code, monotonic() - started, response_data)

        return status_code, response_data
    except Exception:
        log.exception('Tag default update failed after %.2fs', monotonic() - started)
        raise
    finally:
        flush_logging()
