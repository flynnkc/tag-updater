#/usr/bin/python3.11

import datetime
import logging
from typing import Any

from oci import identity
from oci import pagination
from oci.exceptions import ServiceError
from oci.signer import Signer
from os import getenv

class TagUpdater:
    def __init__(
        self,
        config: dict[str, str],
        compartments: list[str],
        signer: Signer | None = None,
    ) -> None:
        self.log = logging.getLogger(__name__)
        self.config = config
        self.compartments = compartments
        self.client = identity.IdentityClient(config, signer=signer)

    # Entrypoint method to change tags
    def update_tags(self, namespace: str, key: str) -> tuple[int, str]:
        errors: list[str] = []  # Collect errors outside the loop.
        matched = 0
        updated = 0

        # OCI likes to treat non-success responses as exceptions -- prevent it
        # from stopping execution with try/except
        try:
            defaults = self.get_tag_defaults(namespace, key)
            matched = len(defaults)
            if not defaults:
                self.log.info('No matching tag defaults for %s.%s; no updates needed',
                              namespace, key)
            for default in defaults:
                details = identity.models.UpdateTagDefaultDetails(
                    is_required=default.is_required,
                    value=self.get_value()
                )

                self.log.debug('Updating tag default %s with %s', default.id,
                               details.value)
                
                try:
                    self.client.update_tag_default(default.id, details)
                    updated += 1
                    self.log.info('Updated tag default %s (%s.%s): value=%s',
                                  default.id, namespace, key, details.value)
                except ServiceError as e:
                    error = (f'{e.status} - {e.operation_name} - '
                                f'{default.tag_definition_name}/{default.id}')
                    self.log.error(error)
                    errors.append(error)

        except (ServiceError, ValueError) as e:
            if isinstance(e, ValueError):
                error = str(e)
            else:
                error = f'{e.status} - {e.operation_name} - {namespace}.{key}'
            self.log.error(error)
            errors.append(error)

        self.log.log(logging.ERROR if errors else logging.INFO,
                     'Tag default update summary for %s.%s: matched=%d updated=%d '
                     'errors=%d', namespace, key, matched, updated, len(errors))

        # Unhappy path
        if errors:
            return (400, ', '.join(errors))
        
        return (200, 'Updates complete') # Happy path


    # Change this method to determine tag value
    def get_value(self) -> str:
        ### Change here ###

        # I want to set the tag to a date in the format yyyy-mm-dd
        expiration_date = datetime.date.today() + datetime.timedelta(
            days=int(getenv('DAYS', '90'))
        )
        return expiration_date.strftime('%Y-%m-%d')
    
        ### End changes ###

    # Return list of tag defaults
    def get_tag_defaults(self, namespace: str, key: str) -> list[Any]:
        ns_id = self.get_tag_namespace(namespace)

        defaults: list[Any] = []
        for cmp in self.compartments:
            self.log.info('Listing tag defaults in compartment %s', cmp)
            response = pagination.list_call_get_all_results(
                self.client.list_tag_defaults, compartment_id=cmp)
            
            matches = 0
            for result in response.data:
                if result.tag_definition_name == key and result.tag_namespace_id == ns_id:
                    defaults.append(result)
                    matches += 1
            self.log.info('Compartment %s: scanned=%d matched=%d for %s.%s',
                          cmp, len(response.data), matches, namespace, key)

        self.log.debug('Found tag defaults %s',
                       ', '.join(default.id for default in defaults))
        return defaults

    def get_tag_namespace(self, namespace: str) -> str:
        self.log.info('Resolving tag namespace %s in tenancy %s',
                      namespace, self.config['tenancy'])
        response = pagination.list_call_get_all_results(
            self.client.list_tag_namespaces,
            self.config['tenancy'],
            include_subcompartments=True
        )

        for item in response.data:
            if item.name == namespace:
                self.log.info('Resolved tag namespace %s: %s', namespace, item.id)
                return item.id

        raise ValueError(f'Tag namespace not found: {namespace}')
