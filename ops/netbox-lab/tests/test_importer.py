"""Actual importer module logic against an isolated in-memory HTTP boundary."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3] / 'playbooks/development/netbox'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


client = load('ansible.module_utils.fhs_netbox', ROOT / 'module_utils/fhs_netbox.py')
module = load('offline_fpga_sync', ROOT / 'library/fhs_fpga_sync.py')


class MemorySync(client.Sync):
    def __init__(self, tables, check):
        self.tables = copy.deepcopy(tables)
        self.check = check
        self.plan = []
        self.cache = {}
        self.virtual = -1
        self.writes = []

    def request(self, method, path, **kwargs):
        if method == 'GET':
            filters = kwargs.get('params', {})
            rows = self.tables.get(path, [])
            def matches(row):
                for key, value in filters.items():
                    if key == 'limit':
                        continue
                    field = key[:-3] if key.endswith('_id') else key
                    if client.scalar(row.get(field)) != value:
                        return False
                return True
            rows = [copy.deepcopy(row) for row in rows if matches(row)]
            return {'count': len(rows), 'results': rows[:filters.get('limit', 100)], 'next': None}
        self.writes.append((method, path, copy.deepcopy(kwargs['json'])))
        if method == 'POST':
            rows = self.tables.setdefault(path, [])
            row = dict(kwargs['json'], id=10000 + sum(len(r) for r in self.tables.values()))
            rows.append(row)
        else:
            table, pk = path.rstrip('/').rsplit('/', 1)
            row = next(r for r in self.tables[table + '/'] if r['id'] == int(pk))
            row.update(kwargs['json'])
        return copy.deepcopy(row)


def fixture():
    card = {'serial': 'original-A', 'part': 'ConnectX', 'bay': 'NIC 0000:01:00',
            'position': '0000:01:00', 'interfaces': [{'name': 'eth1', 'type': 'other'}]}
    tables = {
        'dcim/devices/': [{'id': 1, 'name': 'server', 'site': 88, 'rack': 99}],
        'dcim/manufacturers/': [{'id': 2, 'name': 'Mellanox'}],
        'dcim/module-types/': [{'id': 3, 'manufacturer': 2, 'model': 'FHS NIC staging (no components)'},
                               {'id': 4, 'manufacturer': 2, 'model': 'ConnectX', 'part_number': 'ConnectX'}],
        'dcim/module-bays/': [{'id': 5, 'device': 1, 'name': card['bay'], 'position': card['position']}],
        'dcim/modules/': [{'id': 6, 'device': 1, 'module_bay': 5, 'module_type': 4,
                          'serial': card['serial'], 'status': 'active', 'custom_fields': {'manual': 'keep'}}],
        'dcim/interfaces/': [{'id': 7, 'device': 1, 'name': 'eth1', 'module': 6,
                              'type': '100gbase-x-qsfp28', 'description': 'manual', 'primary_mac_address': 42}],
        'extras/custom-fields/': [{'id': 20+i, 'name': name, 'type': kind, 'object_types': ['dcim.module']}
                                 for i, (name, kind) in enumerate((('nic_driver', 'text'), ('nic_firmware', 'text'),
                                        ('nic_functions', 'json'), ('pci_endpoints', 'json')))],
    }
    return tables, {'device': 'server', 'kind': 'NIC', 'cards': [card]}


class ImporterTests(unittest.TestCase):
    def run_sync(self, tables, params, check=False):
        sync = MemorySync(tables, check)
        with patch.object(module, 'Sync', return_value=sync):
            result = module.synchronize(params, check)
        return sync, result

    def test_existing_manual_facts_and_unchanged_rerun(self):
        tables, params = fixture()
        sync, result = self.run_sync(tables, params)
        self.assertEqual(result, [])
        self.assertEqual(sync.writes, [])
        self.assertEqual(sync.tables, tables)
        sync, result = self.run_sync(sync.tables, params)
        self.assertEqual(result, [])

    def test_firmware_update_preserves_identity_manual_fields_and_interface(self):
        tables, params = fixture()
        params['cards'][0]['firmware'] = 'observed-2'
        sync, result = self.run_sync(tables, params)
        self.assertTrue(result)
        self.assertEqual(sync.tables['dcim/modules/'][0]['serial'], 'original-A')
        self.assertEqual(sync.tables['dcim/modules/'][0]['custom_fields']['manual'], 'keep')
        self.assertEqual(sync.tables['dcim/interfaces/'], tables['dcim/interfaces/'])
        self.assertFalse(any('serial' in data for _, _, data in sync.writes))
        again, result = self.run_sync(sync.tables, params)
        self.assertEqual(again.writes, [])
        self.assertEqual(result, [])

    def test_check_mode_actual_update_has_zero_writes(self):
        tables, params = fixture()
        params['cards'][0]['firmware'] = 'observed-2'
        sync, result = self.run_sync(tables, params, check=True)
        self.assertTrue(result)
        self.assertEqual(sync.writes, [])
        self.assertEqual(sync.tables, tables)

    def test_disappearance_preserves_hardware_and_transceiver_history(self):
        tables, params = fixture()
        tables['dcim/inventory-items/'] = [{'id': 55, 'name': 'optic', 'serial': 'original-optic'}]
        params['cards'] = []
        sync, result = self.run_sync(tables, params)
        self.assertEqual(sync.tables, tables)
        self.assertEqual(sync.writes, [])
        self.assertEqual(result, [])

    def test_replacement_fails_before_writes_until_native_schema_resolved(self):
        tables, params = fixture()
        params['cards'][0]['serial'] = 'new-B'
        for check in (False, True):
            sync = MemorySync(tables, check)
            with patch.object(module, 'Sync', return_value=sync), self.assertRaisesRegex(ValueError, 'unused-inventory schema'):
                module.synchronize(params, check)
            self.assertEqual(sync.writes, [])
            self.assertEqual(sync.tables, tables)

    def test_cross_device_and_bay_identity_conflicts_never_write(self):
        for field, value in (('device', 999), ('module_bay', 999)):
            tables, params = fixture()
            tables['dcim/modules/'][0][field] = value
            sync = MemorySync(tables, False)
            with patch.object(module, 'Sync', return_value=sync), self.assertRaises(ValueError):
                module.synchronize(params, False)
            self.assertEqual(sync.writes, [])

    def test_duplicate_serial_discovery_never_writes(self):
        tables, params = fixture()
        params['cards'].append(copy.deepcopy(params['cards'][0]))
        sync = MemorySync(tables, False)
        with patch.object(module, 'Sync', return_value=sync), self.assertRaises(ValueError):
            module.synchronize(params, False)
        self.assertEqual(sync.writes, [])
