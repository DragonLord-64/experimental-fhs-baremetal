"""Offline contracts for ownership, native facts, pagination and fail-closed export."""
import copy
import importlib.util
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import inventory as lab


class MemoryAPI:
    def __init__(self):
        self.data = {}
        self.writes = []
        self.sequence = 0
        self.token = 'synthetic-test-only'

    def records(self, path, **filters):
        rows = copy.deepcopy(self.data.get(path, []))
        if path == 'dcim/devices/' and 'tag' in filters:
            tags = filters['tag'] if isinstance(filters['tag'], list) else [filters['tag']]
            rows = [r for r in rows if all(lab.tagged(r, t) for t in tags)
                    and r['site']['slug'] == filters['site'] and r['status']['value'] == filters['status']]
        if path == 'dcim/devices/' and 'name' in filters:
            rows = [r for r in rows if r['name'] == filters['name']]
        if path == 'ipam/ip-addresses/' and 'address' in filters:
            rows = [r for r in rows if r['address'] == filters['address']]
        if path == 'ipam/ip-addresses/' and 'device_id' in filters:
            ports = {r['id'] for r in self.data.get('dcim/interfaces/', [])
                     if lab.ident(r['device']) in filters['device_id']}
            rows = [r for r in rows if r.get('assigned_object_type') == 'dcim.interface'
                    and r.get('assigned_object_id') in ports]
        if path == 'dcim/interfaces/' and filters:
            identities = filters['device_id']
            if not isinstance(identities, list):
                identities = [identities]
            rows = [r for r in rows if lab.ident(r['device']) in identities]
        return rows

    def ref(self, endpoint, identity):
        return copy.deepcopy(next(r for r in self.data[endpoint] if r['id'] == identity))

    def call(self, path, method='GET', data=None):
        self.writes.append((path, method, copy.deepcopy(data)))
        if method in ['GET', 'DELETE']:
            endpoint, identity, _ = path.rsplit('/', 2)
            endpoint += '/'
            row = next(r for r in self.data[endpoint] if r['id'] == int(identity))
            if method == 'DELETE':
                self.data[endpoint].remove(row)
                return None
            return copy.deepcopy(row)
        if method == 'PATCH':
            endpoint, identity, _ = path.rsplit('/', 2)
            endpoint += '/'
            row = next(r for r in self.data[endpoint] if r['id'] == int(identity))
            for key, value in data.items():
                if key == 'tags':
                    row[key] = [self.ref('extras/tags/', v) for v in value]
                elif key == 'status':
                    row[key] = {'value': value}
                else:
                    source = 'dcim/mac-addresses/' if key == 'primary_mac_address' else 'ipam/ip-addresses/'
                    row[key] = self.ref(source, value)
            return copy.deepcopy(row)
        if method != 'POST':
            raise AssertionError('unexpected method')
        results = []
        for value in (data if isinstance(data, list) else [data]):
            row = copy.deepcopy(value)
            self.sequence += 1
            row['id'] = self.sequence
            if 'tags' in row:
                row['tags'] = [self.ref('extras/tags/', t) for t in row['tags']]
            for key, endpoint in [('site', 'dcim/sites/'), ('device', 'dcim/devices/')]:
                if key in row:
                    row[key] = self.ref(endpoint, row[key])
            if 'status' in row:
                row['status'] = {'value': row['status']}
            self.data.setdefault(path, []).append(row)
            results.append(copy.deepcopy(row))
        return results if isinstance(data, list) else results[0]


def small_topology():
    return {'units': [{'name': 'VCCUnit1'}],
            'hosts': [{'name': 'vccunit1-fhs1', 'unit': 'VCCUnit1', 'role': 'vcc',
                       'management_ip': '192.0.2.1', 'chassis_mac': '02:00:00:01:01:00', 'interfaces': [
                           {'node_device': 'enp1s0f0', 'node_mac': '02:00:00:01:01:01'}]}],
            'switches': [{'name': 'VCCUnit1-switch', 'unit': 'VCCUnit1', 'role': 'vcc',
                          'management_ip': '192.0.2.201', 'chassis_mac': '02:00:00:ff:01:00', 'links': [{'local_port': 'eth1/21/1'}]}]}


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.api = MemoryAPI()
        lab.seed(self.api, small_topology())

    def test_unchanged_rerun_performs_no_writes(self):
        before = copy.deepcopy(self.api.data)
        self.api.writes.clear()
        result = lab.seed(self.api, small_topology())
        self.assertTrue(all(n == 0 for n in result['created'].values()))
        self.assertEqual(self.api.writes, [])
        self.assertEqual(before, self.api.data)

    def test_operator_change_and_cleared_pointers_survive_new_object(self):
        row = self.api.data['dcim/devices/'][0]
        row['primary_ip4'] = None
        row['custom_fields']['fhs_lab']['operator'] = 'preserved'
        port = self.api.data['dcim/interfaces/'][0]
        port['primary_mac_address'] = None
        topology = small_topology()
        topology['hosts'][0]['interfaces'].append({'node_device': 'newport', 'node_mac': '02:00:00:01:01:02'})
        lab.seed(self.api, topology)
        self.assertIsNone(row['primary_ip4'])
        self.assertIsNone(port['primary_mac_address'])
        self.assertEqual(row['custom_fields']['fhs_lab']['operator'], 'preserved')

    def test_unowned_collision_is_not_modified(self):
        self.api.data['dcim/devices/'][0]['tags'] = []
        self.api.writes.clear()
        with self.assertRaises(lab.LabError):
            lab.seed(self.api, small_topology())
        self.assertEqual(self.api.writes, [])

    def test_export_native_fields_and_operator_change(self):
        nodes = lab.export_nodes(self.api)
        self.assertEqual(len(nodes), 3)
        self.assertTrue(all(n['driver'] == 'fake-hardware' for n in nodes.values()))
        row = next(r for r in self.api.data['dcim/devices/'] if lab.tagged(r, 'lab-provisioning'))
        row['primary_ip4']['address'] = '198.51.100.99/32'
        self.assertEqual(lab.export_nodes(self.api)[row['name']]['ipv4_address'], '198.51.100.99')

    def test_inactive_and_unowned_excluded(self):
        rows = self.api.data['dcim/devices/']
        selected = [r for r in rows if lab.tagged(r, 'lab-provisioning')]
        selected[0]['status'] = {'value': 'offline'}
        selected[1]['tags'] = []
        self.assertEqual(len(lab.export_nodes(self.api)), 1)

    def test_failures_invalidate_stale_export_and_private_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'nodes.json'
            self.assertEqual(lab.private_export(self.api, path), 3)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            row = next(r for r in self.api.data['dcim/devices/'] if lab.tagged(r, 'lab-provisioning'))
            row['oob_ip'] = None
            with self.assertRaises(lab.LabError):
                lab.private_export(self.api, path)
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_missing_ambiguous_and_duplicate_mac_rejected(self):
        for failure in ['missing', 'ambiguous', 'duplicate']:
            api = copy.deepcopy(self.api)
            ports = [r for r in api.data['dcim/interfaces/'] if lab.tagged(r, 'provisioning-interface')]
            if failure == 'missing':
                ports[0]['primary_mac_address'] = None
            elif failure == 'ambiguous':
                duplicate = copy.deepcopy(ports[0])
                duplicate['id'] += 999
                api.data['dcim/interfaces/'].append(duplicate)
            else:
                ports[1]['primary_mac_address'] = ports[0]['primary_mac_address']
            with self.subTest(failure=failure), self.assertRaises(lab.LabError):
                lab.export_nodes(api)

    def test_server_ignoring_scope_fails_closed(self):
        with patch.object(self.api, 'records', side_effect=lambda path, **kw: copy.deepcopy(self.api.data[path])):
            with self.assertRaises(lab.LabError):
                lab.export_nodes(self.api)


class ReducedPopulationTests(unittest.TestCase):
    def test_selected_seed_defaults_keep_full_population_identities(self):
        # Independent full-order fixture: FSP identities follow all 24 VCCs;
        # seed BMC/OOB offsets follow all 132 hosts, then all 51 switches.
        full = {'units': [], 'hosts': [], 'switches': []}
        for role, count in [('vcc', 24), ('fsp', 27)]:
            for number in range(1, count + 1):
                unit = f'{role.upper()}Unit{number}'
                index = len(full['units']) + 1
                full['units'].append({'name': unit})
                for host in range(1, 2 if role == 'vcc' else 5):
                    full['hosts'].append({
                        'name': f'{role}unit{number}-fhs{host}', 'unit': unit, 'role': role,
                        'management_ip': f'192.0.2.{len(full["hosts"]) + 1}',
                        'chassis_mac': f'02:00:00:{index:02x}:{host:02x}:00',
                        'interfaces': []})
                full['switches'].append({
                    'name': unit + '-switch', 'unit': unit, 'role': role,
                    'management_ip': f'192.0.2.{200 + index}',
                    'chassis_mac': f'02:00:00:ff:{index:02x}:00', 'links': []})
        selected_units = {f'VCCUnit{n}' for n in range(1, 5)} | {
            f'FSPUnit{n}' for n in range(1, 4)}
        reduced = {key: [copy.deepcopy(row) for row in rows
                        if row.get('unit', row.get('name')) in selected_units]
                   for key, rows in full.items()}
        self.assertEqual((len(full['hosts']), len(full['switches'])), (132, 51))
        self.assertEqual((len(reduced['hosts']), len(reduced['switches'])), (16, 7))
        old, new = MemoryAPI(), MemoryAPI()
        lab.seed(old, full)
        lab.seed(new, reduced)

        def facts(api):
            result = {}
            for device in api.data['dcim/devices/']:
                ports = [p for p in api.data['dcim/interfaces/']
                         if lab.ident(p['device']) == device['id']]
                result[device['name']] = {
                    'primary': device['primary_ip4']['address'],
                    'oob': device['oob_ip']['address'],
                    'macs': {p['name']: p['primary_mac_address']['mac_address']
                             for p in ports if p.get('primary_mac_address')}}
            return result

        old_facts, new_facts = facts(old), facts(new)
        self.assertEqual(len(old_facts) - len(new_facts), 160)
        # Compare every retained logical and all three fake provisioning records.
        for name in sorted(new_facts):
            with self.subTest(name=name):
                self.assertEqual(new_facts[name], old_facts[name])


class HTTPTests(unittest.TestCase):
    def test_endpoint_scope(self):
        for url in ['', 'https://netbox.example/', 'http://localhost:123/netbox/',
                    'http://127.0.0.1:123/', 'http://127.0.0.1:123/netbox/?token=x']:
            with self.subTest(url=url), self.assertRaises(lab.LabError):
                lab.API(url, 'synthetic')
        with self.assertRaises(lab.LabError):
            lab.API('http://127.0.0.1:123/netbox/', '')

    def test_paginated_records_and_duplicate_ids(self):
        api = lab.API('http://127.0.0.1:123/netbox/', 'synthetic')
        pages = [{'results': [{'id': 1}], 'next': api.root + 'dcim/devices/?offset=1'},
                 {'results': [{'id': 2}], 'next': None}]
        with patch.object(api, 'call', side_effect=pages):
            self.assertEqual([r['id'] for r in api.records('dcim/devices/')], [1, 2])
        pages[1]['results'] = [{'id': 1}]
        with patch.object(api, 'call', side_effect=pages), self.assertRaises(lab.LabError):
            api.records('dcim/devices/')

    def test_foreign_pagination_and_redirect_blocked_before_request(self):
        api = lab.API('http://127.0.0.1:123/netbox/', 'synthetic')
        with self.assertRaises(lab.LabError):
            api.call('https://example.invalid/api/')
        with self.assertRaises(lab.LabError):
            lab.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.invalid')


if __name__ == '__main__':
    unittest.main()
