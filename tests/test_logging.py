import logging
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from oci.exceptions import ServiceError

from modules import app
from modules import signer
from modules.tagupdater import TagUpdater


class TagUpdaterLoggingTests(unittest.TestCase):
    def setUp(self):
        client_patch = patch('modules.tagupdater.identity.IdentityClient')
        self.client = client_patch.start().return_value
        self.addCleanup(client_patch.stop)
        self.updater = TagUpdater({'tenancy': 'tenancy'}, ['compartment'])
        self.default = SimpleNamespace(
            id='default-id', is_required=True, tag_definition_name='expiry',
            tag_namespace_id='namespace-id',
        )

    def test_success_logs_discovery_value_and_counts(self):
        responses = [
            SimpleNamespace(data=[SimpleNamespace(name='tags', id='namespace-id')]),
            SimpleNamespace(data=[self.default, SimpleNamespace(
                tag_definition_name='other', tag_namespace_id='namespace-id')]),
        ]
        with patch('modules.tagupdater.pagination.list_call_get_all_results',
                   side_effect=responses), \
                patch.object(self.updater, 'get_value', return_value='2027-01-24'), \
                self.assertLogs('modules.tagupdater', level='INFO') as logs:
            result = self.updater.update_tags('tags', 'expiry')

        self.assertEqual(result, (200, 'Updates complete'))
        output = '\n'.join(logs.output)
        self.assertIn('Resolved tag namespace tags: namespace-id', output)
        self.assertIn('Compartment compartment: scanned=2 matched=1', output)
        self.assertIn('Updated tag default default-id (tags.expiry): value=2027-01-24', output)
        self.assertIn('matched=1 updated=1 errors=0', output)
        self.client.update_tag_default.assert_called_once()

    def test_no_matches_logs_explicit_no_op(self):
        with patch.object(self.updater, 'get_tag_defaults', return_value=[]), \
                self.assertLogs('modules.tagupdater', level='INFO') as logs:
            result = self.updater.update_tags('tags', 'expiry')
        self.assertEqual(result[0], 200)
        self.assertIn('no updates needed', '\n'.join(logs.output))
        self.assertIn('matched=0 updated=0 errors=0', '\n'.join(logs.output))
        self.client.update_tag_default.assert_not_called()

    def test_partial_failure_counts_only_confirmed_updates(self):
        self.client.update_tag_default.side_effect = [
            ServiceError(403, 'Forbidden', {}, 'Denied', operation_name='update'),
            Mock(),
        ]
        with patch.object(self.updater, 'get_tag_defaults',
                          return_value=[self.default, self.default]), \
                self.assertLogs('modules.tagupdater', level='INFO') as logs:
            result = self.updater.update_tags('tags', 'expiry')
        self.assertEqual(result[0], 400)
        self.assertIn('matched=2 updated=1 errors=1', '\n'.join(logs.output))


class AppLoggingTests(unittest.TestCase):
    def setUp(self):
        env_patch = patch.dict(os.environ, {'TAG_NAMESPACE': 'tags', 'TAG_KEY': 'expiry'},
                               clear=True)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        for name in ('configure_console_logging', 'configure_oci_logging', 'flush_logging'):
            helper_patch = patch.object(app, name)
            helper_patch.start()
            self.addCleanup(helper_patch.stop)

    def test_result_log_level_reflects_status(self):
        for status, level in ((200, logging.INFO), (400, logging.ERROR)):
            with self.subTest(status=status), \
                    patch.object(app, 'create_signer', return_value=(
                        {'tenancy': 'tenancy', 'region': 'home-region'}, Mock())), \
                    patch.object(app, 'TagUpdater') as updater, \
                    self.assertLogs('modules.app', level='INFO') as logs:
                updater.return_value.update_tags.return_value = (status, 'result')
                self.assertEqual(app.run_update(), (status, 'result'))
            self.assertEqual(logs.records[-1].levelno, level)
            self.assertIn(f'status={status} duration=', logs.output[-1])
            self.assertIn('using tenancy root compartment', '\n'.join(logs.output))
            app.flush_logging.assert_called()

    def test_signer_failure_is_logged_and_flushed(self):
        with patch.object(app, 'create_signer', side_effect=ValueError('bad signer')), \
                self.assertLogs('modules.app', level='INFO') as logs, \
                self.assertRaisesRegex(ValueError, 'bad signer'):
            app.run_update()
        self.assertIn('Tag default update failed after', '\n'.join(logs.output))
        app.flush_logging.assert_called_once()

    def test_missing_configuration_is_logged_without_creating_signer(self):
        del os.environ['TAG_KEY']
        with patch.object(app, 'create_signer') as create, \
                self.assertLogs('modules.app', level='ERROR') as logs:
            self.assertEqual(app.run_update()[0], 400)
        create.assert_not_called()
        self.assertIn('TAG_KEY', logs.output[0])

    def test_signer_logs_authentication_type_and_regions(self):
        principal = SimpleNamespace(region='workload-region', tenancy_id='tenancy')
        with patch.object(signer, 'get_resource_principals_signer',
                          return_value=principal), \
                patch.dict(os.environ, {'OCI_IDENTITY_REGION': 'home-region'}), \
                self.assertLogs('modules.signer', level='INFO') as logs:
            signer.create_signer()
        self.assertIn('Creating OCI RESOURCE_PRINCIPAL signer', logs.output[0])
        self.assertIn('signer region=workload-region identity region=home-region',
                      logs.output[-1])


if __name__ == '__main__':
    unittest.main()
