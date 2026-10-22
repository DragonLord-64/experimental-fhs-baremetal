"""Failure contracts for actual CLI invocation and native inventory validation."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import consumers
import exercise
import inventory as lab
from test_inventory import MemoryAPI, small_topology


def plugin_result(api):
    hosts, groups = {}, {}
    for row in api.records('dcim/devices/', tag=lab.OWNER, site=lab.SITE, status='active'):
        kind = row['custom_fields']['fhs_lab']['kind']
        ports = api.records('dcim/interfaces/', device_id=row['id'])
        for port in ports:
            port['tags'] = [t['slug'] for t in port['tags']]
            port['ip_addresses'] = [{k: v for k, v in ip.items() if k not in
                {'assigned_object_id', 'assigned_object_type', 'assigned_object'}}
                for ip in api.records('ipam/ip-addresses/', device_id=[row['id']])
                if ip['assigned_object_id'] == port['id']]
        hosts[row['name']] = {'ansible_host': row['primary_ip4']['address'].split('/')[0],
            'primary_ip4': row['primary_ip4']['address'].split('/')[0],
            'oob_ip': row['oob_ip']['address'].split('/')[0],
            'custom_fields': copy.deepcopy(row['custom_fields']), 'interfaces': ports}
        groups.setdefault('lab_' + kind, {'hosts': []})['hosts'].append(row['name'])
    return {'_meta': {'hostvars': hosts}, **groups}


class ConsumerTests(unittest.TestCase):
    def test_assigned_interface_ips_reject_missing_stale_and_moved_addresses(self):
        api = MemoryAPI()
        lab.seed(api, small_topology())
        result = plugin_result(api)
        consumers.assert_inventory(api, result)
        for mutation in ['missing', 'stale', 'moved']:
            bad = copy.deepcopy(result)
            ports = next(iter(bad['_meta']['hostvars'].values()))['interfaces']
            port = next(p for p in ports if p['ip_addresses'])
            if mutation == 'missing':
                port['ip_addresses'] = []
            elif mutation == 'stale':
                port['ip_addresses'][0]['address'] = '192.0.2.254/32'
            else:
                other = next(p for p in ports if p is not port)
                other['ip_addresses'], port['ip_addresses'] = port['ip_addresses'], []
            with self.subTest(mutation=mutation), self.assertRaisesRegex(lab.LabError, 'assigned IP mismatch'):
                consumers.assert_inventory(api, bad)

    def test_native_interfaces_one_scoped_bulk_read_preserves_exact_checks(self):
        api = MemoryAPI()
        lab.seed(api, small_topology())
        result = plugin_result(api)
        with patch.object(api, 'records', wraps=api.records) as reads:
            consumers.assert_inventory(api, result)
        interface_reads = [call for call in reads.call_args_list
                           if call.args == ('dcim/interfaces/',)]
        self.assertEqual(len(interface_reads), 1)
        self.assertEqual(set(interface_reads[0].kwargs['device_id']),
                         {r['id'] for r in api.data['dcim/devices/']})
        ip_reads = [call for call in reads.call_args_list
                    if call.args == ('ipam/ip-addresses/',)]
        self.assertEqual(len(ip_reads), 1)
        self.assertEqual(ip_reads[0].kwargs,
                         {'device_id': interface_reads[0].kwargs['device_id'],
                          'assigned_to_interface': 'true'})
        # An interface losing its tag must remain in the native comparison.
        api.data['dcim/interfaces/'][0]['tags'] = []
        with self.assertRaisesRegex(lab.LabError, 'interface tags mismatch'):
            consumers.assert_inventory(api, result)
        result = plugin_result(api)
        api.data['dcim/interfaces/'][0]['name'] = 'synthetic-renamed'
        with self.assertRaisesRegex(lab.LabError, 'interface names mismatch'):
            consumers.assert_inventory(api, result)

    def test_actual_ansible_inventory_json_string_markers(self):
        # Match the pinned CLI's inventory serialization, not a YAML-only mock.
        import tempfile
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'ANSIBLE_LOCAL_TEMP': directory}):
            from ansible._internal._json._profiles import _inventory_legacy
        value = {'_meta': {'hostvars': {'lab-nb-synthetic': {
            'ansible_host': '192.0.2.1'}}}}
        encoded = json.dumps(value, cls=_inventory_legacy.Encoder)
        self.assertIn('__ansible_unsafe', encoded)
        decoded = json.loads(encoded, object_hook=consumers.inventory_value)
        self.assertEqual(decoded['_meta']['hostvars']['lab-nb-synthetic']['ansible_host'], '192.0.2.1')
        with self.assertRaises(lab.LabError):
            json.loads('{"__ansible_unsafe": 123}', object_hook=consumers.inventory_value)

    def test_diagnostics_keep_actionable_categories_without_record_values(self):
        stderr = ('Failed to parse private-host at https://private.invalid/?token=secret: '
                  "ModuleNotFoundError: No module named 'private-module'; "
                  'AnsibleParserError: unable to parse private-record')
        diagnostic = consumers.failure_category(stderr)
        self.assertIn('missing Python dependency', diagnostic)
        self.assertIn('inventory source parse failed', diagnostic)
        self.assertIn('ModuleNotFoundError', diagnostic)
        for private in ['private-host', 'private.invalid', 'secret', 'private-module', 'private-record']:
            self.assertNotIn(private, diagnostic)
        self.assertEqual(consumers.failure_category('private-record'),
                         'unclassified sanitized CLI failure')

    def test_api_failure_reports_status_without_private_body_or_url(self):
        import io
        import urllib.error
        api = lab.API('http://127.0.0.1:123/netbox/', 'synthetic-test-only')
        error = urllib.error.HTTPError('http://private.invalid/secret', 403,
            'private-message', {}, io.BytesIO(b'private-record'))
        with patch.object(api.opener, 'open', side_effect=error):
            with self.assertRaises(lab.LabError) as caught:
                api.call('dcim/devices/')
        self.assertEqual(str(caught.exception), 'Lab API request failed (GET, devices, HTTP 403)')

    def test_api_transport_diagnostics_are_fixed_and_resource_scoped(self):
        import urllib.error
        api = lab.API('http://127.0.0.1:123/netbox/', 'synthetic-test-only')
        for reason, expected in [(TimeoutError('private'), 'timeout'),
                                 (ConnectionRefusedError('private'), 'connection refused'),
                                 (OSError('private'), 'connection unavailable')]:
            with self.subTest(reason=type(reason).__name__), \
                    patch.object(api.opener, 'open', side_effect=urllib.error.URLError(reason)):
                with self.assertRaises(lab.LabError) as caught:
                    api.call('dcim/interfaces/?private=secret')
                self.assertEqual(str(caught.exception),
                    'Lab API request failed (GET, interfaces, ' + expected + ')')

    def test_native_validation_rejects_stale_facts_and_groups(self):
        api = MemoryAPI()
        lab.seed(api, small_topology())
        result = plugin_result(api)
        self.assertEqual(consumers.assert_inventory(api, result), {'logical': 2, 'provisioning': 3, 'reachable': 0})
        name = next(iter(result['_meta']['hostvars']))
        for field in ['ansible_host', 'oob_ip', 'custom_fields', 'interfaces']:
            bad = copy.deepcopy(result)
            bad['_meta']['hostvars'][name][field] = None
            with self.subTest(field=field), self.assertRaises(lab.LabError):
                consumers.assert_inventory(api, bad)
        bad = copy.deepcopy(result)
        bad['lab_provisioning']['hosts'] = []
        with self.assertRaises(lab.LabError):
            consumers.assert_inventory(api, bad)

    def test_plugin_omits_null_custom_fields_but_preserves_non_null_values(self):
        api = MemoryAPI()
        lab.seed(api, small_topology())
        for row in api.data['dcim/devices/']:
            row['custom_fields']['unused'] = None
        result = plugin_result(api)
        for host in result['_meta']['hostvars'].values():
            del host['custom_fields']['unused']
        consumers.assert_inventory(api, result)
        next(iter(result['_meta']['hostvars'].values()))['custom_fields']['unexpected'] = 'synthetic'
        with self.assertRaises(lab.LabError):
            consumers.assert_inventory(api, result)

    def test_cli_errors_and_empty_inventory_fail_not_silent_fallback(self):
        api = lab.API('http://127.0.0.1:123/netbox/', 'synthetic-test-only')
        for response in [subprocess.CompletedProcess([], 1, '', 'private diagnostic'),
                         subprocess.CompletedProcess([], 0, '{"_meta":{"hostvars":{}}}', ''),
                         subprocess.CompletedProcess([], 0, 'invalid', '')]:
            with patch.object(consumers, 'check_runtime'), patch.object(consumers.subprocess, 'run', return_value=response):
                with self.assertRaises(lab.LabError) as error:
                    consumers.ansible_inventory(api)
                self.assertNotIn('private diagnostic', str(error.exception))
                self.assertNotIn(api.token, str(error.exception))

    def test_exercise_restores_facts_and_deletes_only_temporary_ip(self):
        api = MemoryAPI()
        lab.seed(api, small_topology())
        before = copy.deepcopy(api.data)
        def inventory(source, binary):
            if isinstance(source, lab.API):
                raise lab.LabError('Unavailable synthetic endpoint')
            return plugin_result(source)
        with patch.object(exercise, 'ansible_inventory', side_effect=inventory), patch.object(exercise.socket, 'socket') as socket:
            socket.return_value.__enter__.return_value.getsockname.return_value = ('127.0.0.1', 12345)
            self.assertTrue(all(exercise.exercise(api, 'unused').values()))
        self.assertEqual(api.data, before)

    def test_exercise_failure_restores_primary_and_removes_temp_ip(self):
        api = MemoryAPI()
        lab.seed(api, small_topology())
        before = copy.deepcopy(api.data)
        with patch.object(exercise, 'ansible_inventory', side_effect=[plugin_result(api), lab.LabError('synthetic failure')]):
            with self.assertRaises(lab.LabError):
                exercise.exercise(api, 'unused')
        self.assertEqual(api.data, before)

    def test_runtime_mismatch_fails(self):
        with patch.object(consumers.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'ansible-inventory [core 2.19.0]', '')):
            with self.assertRaises(lab.LabError):
                consumers.check_runtime('ansible-inventory', {})

    def test_serialization_failure_removes_old_and_temporary_exports(self):
        import tempfile
        api = MemoryAPI()
        lab.seed(api, small_topology())
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'nodes.json'
            destination.write_text('stale')
            with patch.object(lab.json, 'dump', side_effect=OSError('synthetic failure')):
                with self.assertRaises(OSError):
                    lab.private_export(api, destination)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_authentication_failure_invalidates_stale_cli_export(self):
        import live
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'nodes.json'
            destination.write_text('stale')
            with patch.object(sys, 'argv', ['live.py', 'export', '--output', str(destination)]), \
                    patch.object(live, 'connection', side_effect=lab.LabError('Authentication failed')):
                with self.assertRaises(lab.LabError):
                    live.main()
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
