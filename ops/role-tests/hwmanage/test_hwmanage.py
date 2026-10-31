"""Focused contracts; no services or physical lifecycle operations."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts/hwmanage'))
from hwmanage_lib import cli, common, inventory, ironic, provision


class ParserContracts(unittest.TestCase):
    def test_help_has_no_optional_imports(self):
        code = "import sys; sys.path.insert(0, 'scripts/hwmanage'); from hwmanage_lib.cli import main; main(['--help'])"
        result = subprocess.run([sys.executable, '-S', '-c', code], cwd=ROOT, capture_output=True)
        self.assertEqual(result.returncode, 0)
        for argv in (['node', 'deploy', '--help'], ['inventory', 'export', '--help'], ['config', 'dnsmasq', 'add-host', '--help']):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught:
                cli.parser().parse_args(argv)
            self.assertEqual(caught.exception.code, 0)

    def test_target_gates_and_fixed_runbooks(self):
        for argv in (['node', 'clean'], ['provision'], ['run', 'full-provision', '--all', '-e', 'x=y'],
                     ['provision', '--all', '--limit', 'a'], ['node', 'clean', '--all', '--clean']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                cli.parser().parse_args(argv)
        self.assertEqual(cli.parser().parse_args(['config', 'dnsmasq', 'add-host', '--limit', 'a', '--image', 'poap.py']).boot_file, 'poap.py')


class DiagnosticContracts(unittest.TestCase):
    def test_verbose_preserves_stdout_and_exposes_stderr(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'HWMANAGE_VERBOSE': '1'}), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = common.run([sys.executable, '-c',
                                 'import sys; print("payload"); print("detail", file=sys.stderr)'])
        self.assertEqual(result, 'payload\n')
        self.assertIn('payload', stdout.getvalue())
        self.assertIn('detail', stderr.getvalue())

    def test_failure_and_timeout_keep_private_diagnostics(self):
        for code, timeout in [('import sys; print("failure", flush=True); sys.exit(3)', 5),
                              ('import time; print("waiting", flush=True); time.sleep(5)', 0.1)]:
            with patch.dict(os.environ, {'HWMANAGE_VERBOSE': '1'}), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(common.Error) as caught:
                    common.run([sys.executable, '-c', code], timeout=timeout)
            path = Path(str(caught.exception).split('private diagnostics: ', 1)[1].split(';', 1)[0])
            try:
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertTrue(path.read_text().strip())
            finally:
                path.unlink()

    def test_netbox_split_credentials_and_legacy(self):
        with tempfile.TemporaryDirectory() as directory:
            secrets = Path(directory)/'secrets.yml'
            endpoints = Path(directory)/'endpoints.yml'
            secrets.write_text('netbox_token: test-token\n')
            endpoints.write_text('netbox_url: http://netbox.example/mid-cbf-hw/netbox/\n')
            with patch.dict(os.environ, {'FHS_PLATFORM_SECRETS_FILE': str(secrets),
                                         'FHS_PLATFORM_ENDPOINTS_FILE': str(endpoints)}):
                api = inventory.netbox_api()
                self.assertEqual(api.base, 'http://netbox.example/mid-cbf-hw/netbox/api/')
                self.assertEqual(api.session.headers['Authorization'], 'Token test-token')
                # Endpoint override is validated before constructing the API.
                endpoints.write_text('netbox_url: invalid-url\n')
                with self.assertRaises(Exception):
                    inventory.netbox_api()
                endpoints.unlink()
                secrets.write_text('netbox_token: test-token\nnetbox_url: https://legacy.example/\n')
                self.assertEqual(inventory.netbox_api().base, 'https://legacy.example/api/')

    def test_vault_secrets_with_separate_endpoint(self):
        transfer = common.load_module('test_split_transfer', ROOT/'playbooks/netbox/netbox_transfer.py')
        with tempfile.TemporaryDirectory() as directory:
            secrets = Path(directory)/'secrets.yml'
            secrets.write_text('$ANSIBLE_VAULT;1.1;AES256\nplaceholder\n')
            decrypted = subprocess.CompletedProcess([], 0, b'netbox_token: test-token\n', b'')
            with patch.object(transfer.subprocess, 'run', return_value=decrypted):
                self.assertEqual(transfer.credentials(secrets, netbox_url='https://netbox.example/'),
                                 ('https://netbox.example/', 'test-token', True))

    def test_installer_migrates_only_its_old_link(self):
        with tempfile.TemporaryDirectory() as directory:
            bindir = Path(directory)
            link = bindir/'hwmanage'
            for old in ('scripts/hwmanage', 'hwmanage/hwmanage', 'bifrost-infra/hwmanage/hwmanage'):
                link.symlink_to(ROOT/old)
                subprocess.run(['bash', str(ROOT/'scripts/install-hwmanage.sh'), directory],
                               check=True, capture_output=True)
                self.assertEqual(link.resolve(), ROOT/'scripts/hwmanage/hwmanage')
                subprocess.run([str(link), '--help'], check=True, capture_output=True)
                link.unlink()
            link.symlink_to(bindir/'unrelated')
            result = subprocess.run(['bash', str(ROOT/'scripts/install-hwmanage.sh'), directory],
                                    capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(os.readlink(link), str(bindir/'unrelated'))

    def test_verbose_parser_positions(self):
        for argv in (['-v', 'inventory', 'import', '--all'],
                     ['inventory', 'import', '--all', '-vv']):
            self.assertGreater(cli.parser().parse_args(argv).verbose, 0)

    def test_diagnostics_copy_scope(self):
        names = ('scripts/hwmanage/hwmanage', 'scripts/hwmanage/import.yml', 'scripts/hwmanage/README.md',
                 'scripts/install-hwmanage.sh', 'bifrost-infra/docker-compose.yml',
                 'scripts/hwmanage/hwmanage_lib/common.py', 'scripts/hwmanage/hwmanage_lib/cli.py',
                 'scripts/hwmanage/hwmanage_lib/inventory.py', 'playbooks/netbox/netbox_transfer.py',
                 'playbooks/netbox/ironic_import.yml', 'playbooks/netbox/ironic_minimal.py',
                 'docs/src/playbooks/hwmanage.md')
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            sentinel = destination/'site-settings'
            sentinel.write_text('preserve')
            (destination/'scripts').mkdir()
            (destination/'scripts/hwmanage').write_text('old executable')
            subprocess.run([sys.executable, str(ROOT/'ops/security-provisioning/copy-to-official.py'),
                            '--diagnostics-only', directory], check=True, capture_output=True)
            for name in names:
                self.assertEqual((destination/name).read_bytes(), (ROOT/name).read_bytes())
            self.assertEqual(sentinel.read_text(), 'preserve')
            self.assertEqual((destination/'scripts/hwmanage.legacy').read_text(), 'old executable')


class LifecycleContracts(unittest.TestCase):
    def test_rejects_active_maintenance_and_transient(self):
        for state, maintenance in [('active', False), ('cleaning', False), ('available', True)]:
            with self.assertRaises(common.Error):
                ironic.guard(dict(provision_state=state, maintenance=maintenance), 'manage', pipeline=True)
        ironic.guard(dict(provision_state='available'), 'manage')

    def test_inspect_requires_manageable(self):
        ironic.guard(dict(provision_state='manageable'), 'inspect')
        with self.assertRaises(common.Error):
            ironic.guard(dict(provision_state='available'), 'inspect')

    def test_conflicts_before_mutation_and_stale_uuid(self):
        api = Mock()
        api.find_node.return_value = dict(uuid='u', name='a', provision_state='enroll')
        api.ports.return_value = [dict(node_uuid='other', address='00:11:22:33:44:55')]
        with self.assertRaises(common.Error):
            ironic.Ironic(api).reconcile(dict(name='a', nics=[dict(mac='00:11:22:33:44:55')]), create=True)
        api.update_node.assert_not_called()
        api.find_node.return_value = None
        with self.assertRaises(common.Error):
            ironic.Ironic(api).reconcile(dict(uuid='missing', name='a'), create=True)
        api.create_node.assert_not_called()

    def test_native_clean_argv_and_final_state(self):
        client = ironic.Ironic(Mock())
        client.get = Mock(return_value=dict(provision_state='manageable'))
        with patch.object(ironic, 'run') as run:
            client.action(dict(uuid='u', provision_state='manageable'), 'clean')
        argv = run.call_args.args[0]
        self.assertEqual(argv[:3], ['baremetal', 'node', 'clean'])
        self.assertIn('--clean-steps', argv)
        self.assertEqual(json.loads(run.call_args.kwargs['data']), ironic.DEFAULT_CLEAN)

    def test_bifrost_localhost_and_native_wait(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'deploy-dynamic.yaml').touch()
            calls = []
            def capture(argv, **kwargs):
                values = json.loads(Path(argv[argv.index('-e')+1][1:]).read_text())
                calls.append((argv, values))
            with patch.dict(os.environ, HWMANAGE_BIFROST_PLAYBOOKS=directory), patch.object(provision, 'run', side_effect=capture), patch.object(ironic, 'credentials', return_value={}):
                provision.bifrost_deploy(dict(name='a'))
            argv, values = calls[0]
            self.assertEqual(argv[argv.index('--limit')+1], 'localhost,a')
            self.assertGreaterEqual(values['wait_timeout'], 900)
            self.assertNotIn('wait_for_node_deploy_timeout', values)

    def test_protected_credentials_win(self):
        with patch.object(ironic.Path, 'exists', return_value=True), patch.object(ironic, 'protected_yaml', return_value={'defaults': {'ipmi_password': 'protected'}}):
            value = ironic.credentials({'driver_info': {'ipmi_password': '******'}})
        self.assertEqual(value['ipmi_password'], 'protected')


class ProvisionContracts(unittest.TestCase):
    def test_yaml_offline_provision_uses_site_vars(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, 'nodes.yml')
            source.write_text('a:\n  driver: ipmi\n  ipv4_address: 192.0.2.1\n  nics: []\n')
            with patch.object(inventory, 'netbox_api', side_effect=AssertionError('NetBox used')), patch.object(provision, 'run') as run:
                hosts = inventory.resolve(str(source))
                provision.apply(hosts)
            argv = run.call_args.args[0]
            self.assertIn(str(provision.site_vars_source()), argv)
            self.assertEqual(argv[argv.index('--limit')+1], 'a')

    def test_inline_vars_private_and_scope_reserved(self):
        try:
            import ansible
        except ImportError:
            self.skipTest('Native Ansible unavailable')
        options = SimpleNamespace(extra_vars=['key=value', 'second="two words"'], tags=None, skip_tags=None)
        with tempfile.TemporaryDirectory() as directory:
            argv = provision.ansible_options(options, directory)
            self.assertNotIn('key=value', argv)
            path = Path(argv[1][1:])
            self.assertEqual(json.loads(path.read_text()), {'key': 'value', 'second': 'two words'})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            options.extra_vars = ['netbox_import_hosts=all']
            with self.assertRaises(common.Error):
                provision.ansible_options(options, directory)

    def test_runbook_orders_sdk_before_collection(self):
        client = Mock()
        client.reconcile.return_value = dict(uuid='u', provision_state='manageable')
        client.get.return_value = dict(uuid='u', provision_state='available', automated_clean=False)
        events = []
        def apply(hosts, **kwargs):
            events.append('inventory' if kwargs.get('inventory_only') else 'wait' if kwargs.get('wait_only') else 'provision')
        host = dict(name='a', driver='ipmi', ansible_host='192.0.2.30', ipv4_address='192.0.2.30',
                    nics=[{'mac': '02:00:00:00:00:01'}],
                    instance_info={'image_source': 'https://images.example/os.qcow2', 'image_checksum': 'abc123'},
                    properties={'root_device': {'name': '/dev/sda'}})
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'deploy-dynamic.yaml').touch()
            with patch.dict(os.environ, HWMANAGE_BIFROST_PLAYBOOKS=directory), patch.object(ironic, 'credentials', return_value={
                    'ipmi_address': '192.0.2.20', 'ipmi_username': 'operator', 'ipmi_password': 'fixture-password'}), patch.object(ironic, 'Ironic', return_value=client), patch.object(provision, 'effective_hosts', side_effect=lambda h:h), patch.object(provision, 'apply', side_effect=apply):
                cli.runbook(SimpleNamespace(action='full-provision'), {'a': host})
        self.assertEqual(events, ['wait', 'provision', 'inventory'])

    def test_inventory_is_opt_in(self):
        text = (ROOT/'playbooks/site.yml').read_text()
        self.assertIn('tags: [never, inventory]', text)
        self.assertIn('netbox/netbox_import.yml', text)

    def test_portable_export_private_and_sanitized(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, 'export')
            with patch.object(provision, 'effective_hosts', side_effect=lambda h:h):
                inventory.export({'a': dict(name='a', driver_info={'ipmi_password': 'hidden'}, host_groups=['baremetal'])}, output_dir=output)
            for file in output.rglob('*'):
                if file.is_file():
                    self.assertEqual(file.stat().st_mode & 0o777, 0o600)
                    self.assertNotIn('hidden', file.read_text())
            self.assertTrue((output/'inventory.yml').exists())
            self.assertTrue((output/'group_vars/baremetal').exists())


class SystemCheckContracts(unittest.TestCase):
    def test_recent_errors_are_bounded_and_fail_without_echoing_payload(self):
        from hwmanage_lib import checks
        with patch.object(checks, 'run', return_value='private service payload') as native:
            with self.assertRaises(common.Error) as caught:
                checks.recent_errors('ironic-api')
        self.assertNotIn('private service payload', str(caught.exception))
        self.assertIn('--lines', native.call_args.args[0])
        with patch.object(checks, 'run', return_value=''):
            self.assertTrue(checks.recent_errors('ironic-api'))

    def test_ansible_validation_uses_native_syntax_check(self):
        from hwmanage_lib import checks
        with patch.object(checks, 'run') as native:
            self.assertTrue(checks.ansible_syntax())
        self.assertIn('--syntax-check', native.call_args.args[0])
        self.assertIn(provision.site_vars_source(), native.call_args.args[0])


class MinimalImportContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helper = common.load_module('minimal_contract', ROOT/'playbooks/netbox/ironic_minimal.py')

    def test_standalone_playbook_uses_shared_import_without_cli(self):
        text = (ROOT/'playbooks/netbox/ironic_import.yml').read_text()
        self.assertIn('ironic_minimal.py', text)
        self.assertNotIn("'inventory', 'import'", text)
        client = Mock()
        with patch.object(self.helper, 'import_selected', return_value=[]) as service, \
                patch.object(ironic, 'Ironic', return_value=client):
            self.assertEqual(self.helper.main(['--all', '--plan']), 0)
        client.targets.assert_called_once_with(None)
        service.assert_called_once_with(client.targets.return_value, client, plan=True)

    def test_batch_continues_after_read_conflict_and_apply_failures(self):
        nodes = {u: {'uuid': u} for u in ('missing', 'conflict', 'write-fail', 'good')}
        client = Mock()
        client.inspection.side_effect = lambda u: (_ for _ in ()).throw(ValueError('missing inventory')) if u == 'missing' else u
        def observed(node, record, settings, probe):
            return dict(uuid=node['uuid'], serial=node['uuid'], bmc=node['uuid'])
        def resolve(sync, item):
            if item['uuid'] == 'conflict':
                raise ValueError('identity conflict')
        def apply(sync, item, settings):
            if item['uuid'] == 'write-fail':
                raise ValueError('write failed')
            return item
        with patch.object(self.helper, 'observation', side_effect=observed), \
                patch.object(self.helper, 'resolve_device', side_effect=resolve), \
                patch.object(self.helper, 'apply', side_effect=apply) as write, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(self.helper.ImportFailures) as caught:
                self.helper.import_nodes(nodes, client, {}, Mock())
        self.assertEqual(caught.exception.failures, ['missing', 'conflict', 'write-fail'])
        self.assertEqual([r['uuid'] for r in caught.exception.results], ['good'])
        self.assertEqual([call.args[1]['uuid'] for call in write.call_args_list], ['write-fail', 'good'])

    def test_batch_rejects_all_duplicate_owners_but_imports_other_nodes(self):
        nodes = {u: {'uuid': u} for u in ('a', 'b', 'c')}
        def observed(node, *args):
            return dict(uuid=node['uuid'], serial='duplicate' if node['uuid'] != 'c' else 'unique', bmc=node['uuid'])
        with patch.object(self.helper, 'observation', side_effect=observed), \
                patch.object(self.helper, 'resolve_device'), patch.object(self.helper, 'apply', return_value={}) as write, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(self.helper.ImportFailures) as caught:
                self.helper.import_nodes(nodes, Mock(), {}, Mock())
        self.assertEqual(caught.exception.failures, ['a', 'b'])
        self.assertEqual(write.call_count, 1)
        self.assertEqual(write.call_args.args[1]['uuid'], 'c')

    def test_import_settings_default_and_override(self):
        import fhs_netbox
        api = Mock()
        api.base = 'http://netbox.example/api/'
        api.session.headers = {'Authorization': 'Token test-token'}
        api.session.verify = True
        with patch.object(inventory, 'netbox_api', return_value=api), \
                patch.object(fhs_netbox, 'Sync'), \
                patch.object(self.helper, 'import_nodes', return_value=[]) as apply, \
                patch.dict(os.environ, {}, clear=True):
            self.helper.import_selected({}, Mock(), plan=True)
            settings = apply.call_args.args[2]
            self.assertIsNone(settings['site'])
            self.assertEqual(settings['provisioning_interface'], None)
            with tempfile.TemporaryDirectory() as directory:
                override = Path(directory)/'custom.yml'
                override.write_text('site: 42\nprovisioning_interface: eno1\n')
                os.environ['HWMANAGE_IMPORT_DEFAULTS'] = str(override)
                self.helper.import_selected({}, Mock(), plan=True)
                self.assertEqual(apply.call_args.args[2]['site'], 42)
                self.assertEqual(apply.call_args.args[2]['provisioning_interface'], 'eno1')

    def test_repeated_import_preserves_operator_fields(self):
        old = dict(id=10, serial='SERIAL123', name='approved', primary_ip4={'id': 90},
                   tags=[{'id': 8}], config_context={'profile': 'approved'},
                   custom_fields={'ironic_uuid': 'u'})
        sync = Mock()
        sync.list.side_effect = lambda path, **query: [] if path == 'dcim/interfaces/' else [old] if path == 'dcim/devices/' else []
        sync.find.return_value = None
        sync.ensure.side_effect = lambda path, key, data, label: dict(data, id=key.get('id', 10))
        item = dict(uuid='u', serial='SERIAL123', name='SERIAL123', bmc='192.0.2.1',
                    port=dict(name='eno1', mac='02:00:00:00:00:01'))
        self.helper.apply(sync, item, {})
        update = next(call.args[2] for call in sync.ensure.call_args_list
                      if call.args[0] == 'dcim/devices/' and call.args[1] == {'id': 10} and 'custom_fields' in call.args[2])
        self.assertEqual(update, {'custom_fields': {'ironic_uuid': 'u'}})
        sync.ensure.reset_mock()
        item['uuid'] = 'different'
        with self.assertRaises(ValueError):
            self.helper.apply(sync, item, {})
        sync.ensure.assert_not_called()

    def test_boot_mac_automatically_selects_unique_interface(self):
        record = dict(inventory=dict(boot={'pxe_interface': 'a8:a1:59:fb:a6:bb'},
            interfaces=[dict(name='enp193s0f1np1', mac_address='54:9b:24:2c:a8:41'),
                        dict(name='enp2s0f0', mac_address='a8:a1:59:fb:a6:bb'),
                        dict(name='enp2s0f1', mac_address='a8:a1:59:fb:a6:bc')]))
        self.assertEqual(self.helper.boot_port(record),
                         dict(name='enp2s0f0', mac='a8:a1:59:fb:a6:bb'))
        self.assertEqual(self.helper.boot_port(record, 'enp2s0f0')['name'], 'enp2s0f0')
        with self.assertRaises(ValueError):
            self.helper.boot_port(record, 'enp2s0f1')
        record['inventory']['interfaces'].append(dict(name='duplicate', mac_address='a8:a1:59:fb:a6:bb'))
        with self.assertRaises(ValueError):
            self.helper.boot_port(record)
        record['inventory']['boot'] = {}
        with self.assertRaises(ValueError):
            self.helper.boot_port(record)
        record['inventory']['boot'] = {'pxe_interface': '00:00:00:00:00:00'}
        with self.assertRaises(ValueError):
            self.helper.boot_port(record)


if __name__ == '__main__':
    unittest.main()
