"""Final deployment and standalone import boundaries; no hardware operations."""
import copy
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'bifrost-infra/hwmanage'))
from hwmanage_lib import cli, common, inventory, ironic, provision


def complete_host(name='a'):
    return dict(name=name, driver='redfish', ansible_host='192.0.2.30',
                ipv4_address='192.0.2.30', nics=[{'mac': '02:00:00:00:00:01'}],
                instance_info={'image_source': 'https://images.example/os.qcow2', 'image_checksum': 'abc123'},
                properties={'root_device': {'name': '/dev/sda'}},
                driver_info={'redfish_address': 'https://192.0.2.20'})


class DeploymentGates(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        Path(self.directory.name, 'deploy-dynamic.yaml').touch()
        env = patch.dict(os.environ, HWMANAGE_BIFROST_PLAYBOOKS=self.directory.name)
        env.start()
        self.addCleanup(env.stop)
        credentials = patch.object(ironic, 'credentials', return_value={
            'redfish_address': 'https://192.0.2.20', 'redfish_username': 'operator',
            'redfish_password': 'fixture-password'})
        credentials.start()
        self.addCleanup(credentials.stop)

    def test_complete_inputs_accepted(self):
        provision.deployment_preflight({'a': complete_host()})

    def test_native_root_comparisons_and_opaque_passwords_accepted(self):
        for criterion in ('> 900', '< 2000'):
            host = complete_host()
            host['properties']['root_device'] = {'size': criterion}
            # Synthetic secrets deliberately contain deployment placeholder markers.
            for password in ('Strong<fixture>Password!42', 'REPLACE{{fixture}}<>!', 'null'):
                with self.subTest(criterion=criterion), patch.object(ironic, 'credentials', return_value={
                    'redfish_address': 'https://192.0.2.20', 'redfish_username': 'operator',
                    'redfish_password': password}):
                    provision.deployment_preflight({'a': host})

    def test_missing_or_placeholder_deployment_inputs_refused(self):
        for key in ('image_source', 'image_checksum'):
            for value in ('', 'REPLACE_WITH_APPROVED_VALUE', '<approved_value>', '{{ approved_value }}'):
                with self.subTest(key=key, value=value):
                    host = complete_host()
                    host['instance_info'][key] = value
                    with self.assertRaises(common.Error):
                        provision.deployment_preflight({'a': host})
        for field, value in (('properties', {}), ('nics', [{'mac': 'invalid'}]), ('ipv4_address', '')):
            host = complete_host()
            host[field] = value
            with self.subTest(field=field), self.assertRaises(common.Error):
                provision.deployment_preflight({'a': host})

    def test_missing_image_in_later_host_prevents_all_runbook_writes(self):
        for action in ('provide-node', 'full-provision'):
            for value in (None, 'REPLACE_WITH_APPROVED_VALUE', '<approved_value>'):
                client = Mock()
                bad = complete_host('b')
                if value is None:
                    bad.pop('instance_info')
                else:
                    bad['instance_info']['image_source'] = value
                with self.subTest(action=action, value=value), patch.object(ironic, 'Ironic', return_value=client), patch.object(provision, 'effective_hosts', side_effect=lambda h: h):
                    with self.assertRaises(common.Error):
                        cli.runbook(SimpleNamespace(action=action), {'a': complete_host(), 'b': bad})
                client.reconcile.assert_not_called()
                client.action.assert_not_called()

    def test_node_deploy_validates_entire_selection(self):
        client = Mock()
        bad = complete_host('b')
        bad.pop('instance_info')
        with patch.object(ironic, 'Ironic', return_value=client), patch.object(provision, 'effective_hosts', side_effect=lambda h: h):
            with self.assertRaises(common.Error):
                cli.node_command(SimpleNamespace(action='deploy', plan=False), {'a': complete_host(), 'b': bad})
        client.action.assert_not_called()
        client.reconcile.assert_not_called()

    def test_inspect_does_not_require_image_or_primary_address(self):
        client = Mock()
        client.reconcile.return_value = dict(uuid='u', provision_state='manageable')
        with patch.object(ironic, 'Ironic', return_value=client), patch.object(provision, 'effective_hosts', side_effect=lambda h: h), contextlib.redirect_stdout(io.StringIO()):
            cli.runbook(SimpleNamespace(action='inspect-host'), {'a': {'name': 'a'}})
        client.action.assert_called_once_with(client.reconcile.return_value, 'inspect')

    def test_missing_bmc_auth_or_playbook_refused(self):
        with patch.object(ironic, 'credentials', return_value={}):
            with self.assertRaises(common.Error):
                provision.deployment_preflight({'a': complete_host()})
        for password in (None, '', '   '):
            with patch.object(ironic, 'credentials', return_value={
                'redfish_address': 'https://192.0.2.20', 'redfish_username': 'operator',
                'redfish_password': password}):
                with self.assertRaises(common.Error) as raised:
                    provision.deployment_preflight({'a': complete_host()})
                self.assertEqual(str(raised.exception), 'Deployment requires protected BMC connection and authentication')
        Path(self.directory.name, 'deploy-dynamic.yaml').unlink()
        with self.assertRaises(common.Error):
            provision.deployment_preflight({'a': complete_host()})


class ImportBoundary(unittest.TestCase):
    def test_wrapper_native_playbook_uses_private_fixed_uuid_selection(self):
        selected = {'original': {'uuid': '00000000-0000-0000-0000-000000000001'}}
        for plan in (False, True):
            captured = []
            def run(argv, **kwargs):
                self.assertEqual(argv[0], 'ansible-playbook')
                self.assertIn(common.ROOT/'playbooks/netbox/ironic_import.yml', argv)
                self.assertEqual('--check' in argv, plan)
                path = Path(argv[argv.index('-e')+1][1:])
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                captured.append(json.loads(path.read_text()))
            with patch.object(inventory, 'resolve', return_value=copy.deepcopy(selected)) as resolve, patch.object(common, 'run', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
                cli.dispatch(cli.parser().parse_args(['inventory', 'import', '-i', 'ironic', '--all'] + (['--plan'] if plan else [])))
            resolve.assert_called_once_with('ironic', None)
            self.assertEqual(captured, [{'hwmanage_selected_uuids': [selected['original']['uuid']]}])

    def test_standalone_fixed_selection_never_relists(self):
        helper = common.load_module('final_gate_import', common.ROOT/'playbooks/netbox/ironic_minimal.py')
        uuid = '00000000-0000-0000-0000-000000000001'
        client = Mock()
        client.get.return_value = {'uuid': uuid}
        with patch.object(ironic, 'Ironic', return_value=client), patch.object(helper, 'import_selected', return_value=[]) as apply, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(helper.main(['--selected-uuids', json.dumps([uuid]), '--plan']), 0)
        client.targets.assert_not_called()
        client.get.assert_called_once_with(uuid)
        apply.assert_called_once_with({uuid: {'uuid': uuid}}, client, plan=True)
