"""Focused transfer contracts; controller source checks do not execute behavior."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('transfer', ROOT/'playbooks/netbox/netbox_transfer.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)


class MemoryAPI:
    """Different source/destination IDs and paginated transport checked separately."""
    def __init__(self, offset=0):
        self.cache = {}
        self.records = {}
        self.fields_map = {}
        self.offset = offset
        self.methods = []

    def fields(self, path):
        return self.fields_map[path]

    def rows(self, path, fresh=False):
        return self.records.setdefault(path, [])

    def request(self, method, path, **kwargs):
        self.methods.append(method)
        assert method != 'DELETE'
        if path == 'status/':
            return {'netbox-version': '4.7.0', 'plugins': {}}
        if method == 'POST':
            row = dict(copy.deepcopy(kwargs['json']), id=self.offset+sum(map(len, self.records.values()))+1)
            self.rows(path).append(row)
            return row
        if method == 'PATCH':
            collection, number = path.rstrip('/').rsplit('/', 1)
            row = next(r for r in self.rows(collection+'/') if r['id'] == int(number))
            row.update(copy.deepcopy(kwargs['json']))
            return row
        raise AssertionError((method, path))


def fixture():
    api = MemoryAPI()
    def add(path, **values):
        number = sum(map(len, api.records.values()))+1
        row = dict(values, id=number, url='http://source/prefix/api/'+path+str(number)+'/')
        api.rows(path).append(row)
        api.fields_map.setdefault(path, {}).update({k: {'read_only': k in ('id', 'url'), 'type': 'string'} for k in row})
        return row
    site = add('dcim/sites/', name='SYN-site', slug='syn-site')
    maker = add('dcim/manufacturers/', name='SYN-vendor', slug='syn-vendor')
    dtype = add('dcim/device-types/', manufacturer=maker, model='SYN-model', slug='syn-model', u_height=1)
    role = add('dcim/device-roles/', name='SYN-role', slug='syn-role')
    devices = [add('dcim/devices/', name=n, site=site, device_type=dtype, role=role,
                   description='source', local_context_data={'nested': {'id': 987, 'list': [1, None]}})
               for n in ('SYN-switch', 'SYN-pdu-A', 'SYN-pdu-B', 'SYN-server')]
    switch, a, b, server = devices
    mgmt = add('dcim/interfaces/', device=switch, name='mgmt0', type='1000base-t', enabled=True)
    eth = add('dcim/interfaces/', device=server, name='eth0', type='1000base-t', enabled=False)
    ip = add('ipam/ip-addresses/', vrf=None, address='192.0.2.10/24', dns_name='switch.example',
             assigned_object_type='dcim.interface', assigned_object_id=mgmt['id'])
    switch['primary_ip4'] = ip
    api.fields_map['dcim/devices/']['primary_ip4'] = {'type': 'nested object', 'read_only': False}
    mac = add('dcim/mac-addresses/', mac_address='02:00:00:00:00:01',
              assigned_object_type='dcim.interface', assigned_object_id=mgmt['id'])
    mgmt['primary_mac_address'] = mac
    api.fields_map['dcim/interfaces/']['primary_mac_address'] = {'type': 'nested object', 'read_only': False}
    for pdu, name in ((a, 'PSU1'), (b, 'PSU2')):
        outlet = add('dcim/power-outlets/', device=pdu, name='1', type='iec-60320-c13')
        port = add('dcim/power-ports/', device=server, name=name, type='iec-60320-c14', maximum_draw=500)
        add('dcim/cables/', a_terminations=[{'object_type': 'dcim.poweroutlet', 'object_id': outlet['id']}],
            b_terminations=[{'object_type': 'dcim.powerport', 'object_id': port['id']}], label=name, length=2, length_unit='m')
    add('dcim/cables/', a_terminations=[{'object_type': 'dcim.interface', 'object_id': mgmt['id']}],
        b_terminations=[{'object_type': 'dcim.interface', 'object_id': eth['id']}], label='uplink', status='connected')
    # Restrict only the source fixture's endpoint catalog, not production behavior.
    export = t.Exporter(api)
    export.raw = {p: {r['id']: r for r in rows} for p, rows in api.records.items()}
    export.fields = api.fields_map
    records = []
    for path, rows in export.raw.items():
        for row in rows.values():
            key = export.identity(path, row)
            data = {k: export.encode(path, k, v, row) for k, v in row.items() if k not in ('id', 'url')}
            records.append(dict(path=path, key=key, ref=export.reference(path, row['id'])['$ref'], data=data))
    return api, dict(format='fhs-netbox-inventory', version=1, source=api.request('GET', 'status/'), records=records, issues=[])


class TransferTests(unittest.TestCase):
    def test_transfer_rerun_preview_and_conflicts(self):
        source, document = fixture()
        exporter = t.Exporter(source)
        exporter.raw = {p: {r['id']: r for r in rows} for p, rows in source.records.items()}
        exporter.fields = source.fields_map
        port = source.rows('dcim/interfaces/')[0]
        self.assertEqual(exporter.encode('dcim/inventory-items/', 'component_id', port['id'],
                                        {'component_type': 'dcim.interface'}),
                         exporter.reference('dcim/interfaces/', port['id']))
        dest = MemoryAPI(1000)
        dest.fields_map = copy.deepcopy(source.fields_map)
        dest.rows('dcim/sites/').append(dict(id=999, name='unrelated', slug='unrelated'))
        before = copy.deepcopy(dest.records)
        preview = t.Importer(dest, True).run(document)
        self.assertTrue(preview['complete'], preview)
        self.assertFalse(set(dest.methods) & {'POST', 'PATCH', 'DELETE'})
        # Preview overlays are API-client-local; use a fresh client as a real CLI does.
        dest.records = before
        result = t.Importer(dest).run(document)
        self.assertTrue(result['complete'], result)
        self.assertEqual(len(dest.rows('dcim/cables/')), 3)
        switch = next(r for r in dest.rows('dcim/devices/') if r['name'] == 'SYN-switch')
        ip = dest.rows('ipam/ip-addresses/')[0]
        self.assertEqual(switch['primary_ip4'], ip['id'])
        self.assertGreater(ip['assigned_object_id'], 1000)
        self.assertEqual(switch['local_context_data'], {'nested': {'id': 987, 'list': [1, None]}})
        repeat = t.Importer(dest).run(document)
        self.assertTrue(repeat['complete'], repeat)
        self.assertEqual(repeat['actions'], [])
        self.assertEqual(dest.rows('dcim/sites/')[0]['name'], 'unrelated')
        ip['assigned_object_id'] = 999999
        conflict = t.Importer(dest).run(document)
        self.assertTrue(any('ownership preserved' in i['reason'] for i in conflict['issues']))
        self.assertEqual(ip['assigned_object_id'], 999999)
        dest.rows('dcim/devices/').append(copy.deepcopy(switch) | {'id': 98765})
        conflict = t.Importer(dest).run(document)
        self.assertTrue(any('Ambiguous' in i['reason'] for i in conflict['issues']))
        broken = copy.deepcopy(document)
        broken['records'] = [r for r in broken['records'] if r['path'] != 'dcim/sites/']
        with self.assertRaisesRegex(t.TransferError, 'Missing referenced'):
            t.Importer(dest).run(broken)

    def test_updates_and_occupied_cables(self):
        source, document = fixture()
        dest = MemoryAPI(1000)
        dest.fields_map = copy.deepcopy(source.fields_map)
        self.assertTrue(t.Importer(dest).run(document)['complete'])
        edited = copy.deepcopy(document)
        switch = next(r for r in edited['records'] if r['data'].get('name') == 'SYN-switch')
        switch['data'].pop('description')
        switch['data']['comments'] = ''
        dest.fields_map['dcim/devices/']['comments'] = {'type': 'string', 'read_only': False}
        current = next(r for r in dest.rows('dcim/devices/') if r['name'] == 'SYN-switch')
        current['description'] = 'destination-only'
        current['comments'] = 'clear me'
        self.assertTrue(t.Importer(dest).run(edited)['complete'])
        self.assertEqual(current['description'], 'destination-only')
        self.assertEqual(current['comments'], '')
        cable = dest.rows('dcim/cables/').pop()
        term = cable['a_terminations'][0]
        endpoint = next(r for r in dest.rows(t.CT[term['object_type']]) if r['id'] == term['object_id'])
        endpoint['cable'] = {'id': 999999}
        result = t.Importer(dest).run(edited)
        self.assertTrue(any('Occupied cable endpoint' in i['reason'] for i in result['issues']))
        self.assertEqual(endpoint['cable']['id'], 999999)
        bad = copy.deepcopy(document)
        record = next(r for r in bad['records'] if r['path'] == 'ipam/ip-addresses/')
        record['data']['assigned_object_id'] = 123
        result = t.Importer(dest).run(bad)
        self.assertTrue(any('portable reference' in i['reason'] for i in result['issues']))

    def test_security_and_pagination(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'inventory.json'
            t.private_json(path, {'private': 'inventory'})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                t.private_json(path, {})
        api = t.API('http://example.test/prefix', 'dummy', True)
        seen = []
        def request(method, path):
            seen.append(path)
            return {'results': [{'id': len(seen)}], 'next': 'http://example.test/prefix/api/dcim/sites/?offset=1' if len(seen) == 1 else None}
        api.request = request
        self.assertEqual(len(api.rows('dcim/sites/')), 2)
        real = t.API('http://example.test/prefix', 'dummy', True)
        with self.assertRaises(t.TransferError):
            real.request('DELETE', 'dcim/sites/1/')
        with self.assertRaises(t.TransferError):
            real.request('GET', 'http://evil.test/api/sites/')
        with self.assertRaises(t.TransferError):
            real.request('GET', '/api/sites/')


if __name__ == '__main__':
    unittest.main()
