#/usr/bin/python3.11

import datetime
import logging

from oci import identity
from oci import pagination
from oci.exceptions import ServiceError
from oci.signer import Signer
from os import getenv

class TagUpdater:
    def __init__(self, config: dict, compartments: list[str], signer: Signer=None):
        self.log = logging.getLogger(__name__)
        self.config = config
        self.compartments = compartments
        self.client = identity.IdentityClient(config, signer=signer)

    # Entrypoint method to change tags
    def update_tags(self, namespace: str, key: str) -> tuple[int,str]:
        errors = [] # collect errors outside loop

        # OCI likes to treat non-success responses as exceptions -- prevent it
        # from stopping execution with try/except
        try:
            for default in self.get_tag_defaults(namespace, key):
                details = identity.models.UpdateTagDefaultDetails(
                    is_required=default.is_required,
                    value=self.get_value()
                )

                self.log.debug(f'Updating tag default {default.id} with '
                               f'{details.value}')
                
                try:
                    self.client.update_tag_default(default.id, details)
                except ServiceError as e:
                    error = (f'{e.status} - {e.operation_name} - '
                                f'{default.tag_definition_name}/{default.id}')
                    self.log.error(error)
                    errors.append(error)

        except ServiceError as e:
            error = f'{e.status} - {e.operation_name} - {namespace}.{key}'
            self.log.error(error)
            errors.append(error)

        # Unhappy path
        if errors:
            return (400, ', '.join(errors))
        
        return (200, 'Updates complete') # Happy path


    # Change this method to determine tag value
    def get_value(self) -> str:
        ### Change here ###

        # I want to set the tag to a date in the format yyyy-mm-dd
        date = datetime.date.today() + datetime.timedelta(
            days=int(getenv('DAYS', '90'))
        )
        return date.strftime('%Y-%m-%d')
    
        ### End changes ###

    # Return list of tag defaults
    def get_tag_defaults(self, namespace: str, key: str) -> list[object]:
        ns_id = self.get_tag_namespace(namespace)

        defaults = []
        for cmp in self.compartments:
            response = pagination.list_call_get_all_results(
                self.client.list_tag_defaults, compartment_id=cmp)
            
            for result in response.data:
                if result.tag_definition_name == key and result.tag_namespace_id == ns_id:
                    defaults.append(result)

        self.log.debug(f'Found tag defaults {", ".join([default.id for default in defaults])}')
        return defaults

    def get_tag_namespace(self, namespace) -> str:
        response = pagination.list_call_get_all_results(
            self.client.list_tag_namespaces,
            self.config['tenancy'],
            include_subcompartments=True
        )

        for item in response.data:
            if item.name == namespace:
                return item.id
