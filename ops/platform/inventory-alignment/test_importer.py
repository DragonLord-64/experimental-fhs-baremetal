"""Importer lifecycle regressions with a stateful, in-memory NetBox REST boundary.

No Ansible installation, service, credentials, sockets or hardware are needed.
The fake models pinned plugin serial-change protection and module-delete retention;
it cannot establish compatibility with the real plugin (see HANDOFF.md).
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Only the module's CLI entrypoint needs Ansible; execute its real synchronize().
modules = {name: types.ModuleType(name) for name in (
    'ansible', 'ansible.module_utils', 'ansible.module_utils.basic', 'ansible.errors')}
modules['ansible.module_utils.basic'].AnsibleModule = object
modules['ansible.errors'].AnsibleFilterError = ValueError
with patch.dict(sys.modules, modules):
    filters = load('fhs_inventory_filters_under_test', 'playbooks/netbox/filter_plugins/fhs_inventory.py')
    shared = load('ansible.module_utils.fhs_netbox', 'playbooks/netbox/module_utils/fhs_netbox.py')
    with patch.dict(sys.modules, {'ansible.module_utils.fhs_netbox': shared}):
        importer = load('fhs_fpga_sync_under_test', 'playbooks/netbox/library/fhs_fpga_sync.py')
        inventory = load('fhs_inventory_sync_under_test', 'playbooks/netbox/library/fhs_inventory_sync.py')


ASSETS = 'plugins/inventory/assets/'
MODULES = 'dcim/modules/'
JOURNAL = 'extras/journal-entries/'


def scalar(value):
    return value.get('id', value.get('value')) if isinstance(value, dict) else value


class Response:
    ok = True
    status_code = 200

    def __init__(self, data, ok=True, status_code=200):
        self.data = copy.deepcopy(data)
        self.ok = ok
        self.status_code = status_code

    def json(self):
        return copy.deepcopy(self.data)


class NetBox:
    """REST persistence, filtering, serial synchronization and deletion signals."""
    def __init__(self):
        self.tables = {}
        self.writes = []
        self.history = []
        self.headers = {}
        self.verify = True
        self.next_id = 1

    def add(self, path, **values):
        values = dict(values, id=self.next_id)
        self.next_id += 1
        self.tables.setdefault(path, {})[values['id']] = copy.deepcopy(values)
        return values

    def rows(self, path):
        return list(self.tables.get(path, {}).values())

    def request(self, method, url, **kwargs):
        path = url.split('/api/', 1)[1]
        parts = path.rstrip('/').split('/')
        pk = int(parts.pop()) if parts[-1].isdigit() else None
        endpoint = '/'.join(parts) + '/'
        table = self.tables.setdefault(endpoint, {})
        if method == 'GET':
            if pk is not None:
                return Response(table[pk])
            filters = kwargs.get('params', {})
            rows = self.rows(endpoint)
            for key, value in filters.items():
                if key in ('limit', 'offset', 'ordering'):
                    continue
                field = key[:-3] if key.endswith('_id') else key
                rows = [r for r in rows if scalar(r.get(field)) == value]
            return Response({'count': len(rows), 'results': rows, 'next': None, 'previous': None})
        data = copy.deepcopy(kwargs.get('json', {}))
        if endpoint == MODULES and method == 'PATCH':
            candidate = dict(table[pk], **data)
            for asset in self.rows(ASSETS):
                if scalar(asset.get('module')) == pk:
                    if any((candidate.get(key) or None) != (asset.get(key) or None)
                           for key in ('serial', 'asset_tag')):
                        # 2.7.1 signals.prevent_update_serial_asset_tag raises
                        # AbortRequest; the REST request must fail atomically.
                        return Response({'detail': 'Change serial/tag via asset'}, False, 400)
        self.writes.append((method, endpoint, pk, data))
        if method == 'POST':
            result = self.add(endpoint, **data)
            pk = result['id']
        elif method == 'PATCH':
            table[pk].update(data)
        elif method == 'DELETE':
            del table[pk]
            kind={MODULES:'module','dcim/inventory-items/':'inventoryitem'}.get(endpoint)
            if kind:
                for asset in self.rows(ASSETS):
                    if scalar(asset.get(kind)) == pk:
                        asset.update({kind:None,'status':'stored'})
                        self.history.append(copy.deepcopy(asset))
            return Response(None,status_code=204)
        else:
            raise AssertionError('Unexpected REST operation ' + method)
        result = self.tables[endpoint][pk]
        if endpoint == ASSETS:
            for kind,path in [('module',MODULES),('device','dcim/devices/'),('inventoryitem','dcim/inventory-items/')]:
                if result.get(kind):
                    result['status']='used'
                    hardware=self.tables[path][scalar(result[kind])]
                    hardware.update(serial=result['serial'],asset_tag=result.get('asset_tag'))
                    if kind=='inventoryitem':
                        itype=self.tables.get('plugins/inventory/inventory-item-types/',{}).get(scalar(result.get('inventoryitem_type')),{})
                        hardware['part_id']=itype.get('part_number','')
            self.history.append(copy.deepcopy(result))
        return Response(result)


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.api = NetBox()
        self.device = self.api.add('dcim/devices/', name='SYNTHETIC-FHS-01', serial='CHASSIS-001')
        self.maker = self.api.add('dcim/manufacturers/', name='BittWare', slug='bittware')
        self.module_type = self.api.add('dcim/module-types/', manufacturer=self.maker['id'], model='IA-860M', part_number='IA-860M')
        self.bay = self.api.add('dcim/module-bays/', device=self.device['id'], name='FPGA slot 1', position='1')
        self.params = dict(netbox_url='https://synthetic.invalid', netbox_token='synthetic-test-only',
                           validate_certs=True, device=self.device['name'], kind='FPGA', cards=[])
        self.session = patch.object(shared.requests, 'Session', return_value=self.api)
        self.session.start()
        self.addCleanup(self.session.stop)

    def card(self, serial='FPGA-OLD'):
        return dict(bay=self.bay['name'], position='1', part='IA-860M', serial=serial,
                    interfaces=[dict(name=f'C1-QSFP{i}', type='400gbase-x-qsfpdd') for i in range(3)])

    def installed(self, serial='FPGA-OLD'):
        module = self.api.add(MODULES, device=self.device['id'], module_bay=self.bay['id'],
                              module_type=self.module_type['id'], serial=serial, asset_tag='LAB-001', status='active', custom_fields={})
        asset = self.api.add(ASSETS, serial=serial, asset_tag='LAB-001', status='used',
                             module_type=self.module_type['id'], module=module['id'], storage_location=None)
        self.api.history.append(copy.deepcopy(asset))
        return module, asset

    def run_import(self, cards, **options):
        return importer.synchronize(dict(self.params, cards=cards, **options), False)

    def test_repeated_import_is_idempotent(self):
        self.run_import([self.card()])
        self.api.writes.clear()
        self.assertEqual([], self.run_import([self.card()]))
        self.assertEqual([], self.api.writes)

    def test_missing_or_partial_scan_preserves_installed_records(self):
        module, asset = self.installed()
        self.run_import([], complete=False)
        self.assertEqual(module['id'], self.api.rows(MODULES)[0]['id'])
        self.assertEqual(asset, self.api.rows(ASSETS)[0])
        self.assertEqual([], self.api.writes)

    def test_missing_and_duplicate_serials_refuse_before_writes(self):
        for cards in ([self.card('')],[self.card(),dict(self.card(),bay='FPGA slot 2')]):
            with self.subTest(cards=cards):
                with self.assertRaises(ValueError): self.run_import(cards)
                self.assertEqual([],self.api.writes)

    def test_replacement_preserves_interface_ids(self):
        self.run_import([self.card()])
        ids={v['id'] for v in self.api.rows('dcim/interfaces/')}
        self.run_import([self.card('FPGA-NEW')])
        self.assertEqual(ids,{v['id'] for v in self.api.rows('dcim/interfaces/')})

    def test_observed_replacement_keeps_cabled_interface_and_history(self):
        old,asset=self.installed()
        port=self.api.add('dcim/interfaces/',device=self.device['id'],name='C1-QSFP0',module=old['id'],cable=999)
        self.run_import([self.card('FPGA-NEW')])
        self.assertEqual('FPGA-NEW',self.api.tables[MODULES][old['id']]['serial'])
        self.assertEqual(999,self.api.tables['dcim/interfaces/'][port['id']]['cable'])
        self.assertEqual('stored',self.api.tables[ASSETS][asset['id']]['status'])
        self.assertFalse(any(w[0]=='DELETE' for w in self.api.writes))

    def test_observed_spare_assignment_moves_without_deleting_installations(self):
        old,asset=self.installed()
        spare=self.api.add(ASSETS,serial='FPGA-NEW',module_type=self.module_type['id'],module=999,status='used')
        self.run_import([self.card('FPGA-NEW')])
        self.assertEqual(old['id'],self.api.tables[ASSETS][spare['id']]['module'])
        self.assertIsNone(self.api.tables[ASSETS][asset['id']]['module'])
        self.assertFalse(any(w[0]=='DELETE' for w in self.api.writes))

    def test_preview_does_not_write_to_api(self):
        importer.synchronize(dict(self.params, cards=[self.card()]), True)
        self.assertEqual([], self.api.writes)

    def test_discovered_module_has_one_asset_with_stable_serial_identity(self):
        self.run_import([self.card()])
        assets = self.api.rows(ASSETS)
        self.assertEqual(1, len(assets), 'Importer must create/reconcile the plugin asset')
        original = copy.deepcopy(assets[0])
        self.run_import([self.card()])
        self.assertEqual([original['id']], [a['id'] for a in self.api.rows(ASSETS)])
        self.assertEqual('FPGA-OLD', assets[0]['serial'])
        self.assertEqual(self.api.rows(MODULES)[0]['id'], scalar(assets[0]['module']))

    def test_replacement_preserves_old_asset_serial_and_installation_id(self):
        module, asset = self.installed()
        self.run_import([self.card('FPGA-NEW')])
        old_asset = self.api.tables[ASSETS][asset['id']]
        self.assertEqual('FPGA-OLD', old_asset['serial'], 'Never patch a different physical serial onto installed hardware')
        self.assertIsNone(old_asset['module'])
        self.assertEqual('stored', scalar(old_asset['status']))
        self.assertIn(module['id'], self.api.tables[MODULES])
        self.assertEqual(module['id'], self.api.rows(MODULES)[0]['id'])
        self.assertEqual(['FPGA-NEW', 'FPGA-OLD'], sorted(a['serial'] for a in self.api.rows(ASSETS)))
        self.assertTrue(any(h['id'] == asset['id'] and h['serial'] == 'FPGA-OLD' for h in self.api.history))

    def test_replacement_writes_parent_journal_with_old_new_serial_and_bay(self):
        self.installed()
        self.run_import([self.card('FPGA-NEW')])
        entries = self.api.rows(JOURNAL)
        self.assertTrue(entries, 'Replacement needs a retained parent journal event')
        text = json.dumps(entries)
        for value in ('FPGA-OLD', 'FPGA-NEW', self.bay['name']):
            self.assertIn(value, text)
        self.assertTrue(any(scalar(e.get('assigned_object_id')) == self.device['id'] for e in entries))

    def test_even_complete_empty_scan_preserves_installations(self):
        module, asset = self.installed()
        nic_bay = self.api.add('dcim/module-bays/', device=self.device['id'], name='NIC slot 1', position='N1')
        nic = self.api.add(MODULES, device=self.device['id'], module_bay=nic_bay['id'], module_type=self.module_type['id'], serial='NIC-001', status='active')
        self.run_import([], complete=True)
        self.assertIn(module['id'], self.api.tables[MODULES], 'Absence must never remove hardware')
        self.assertIn(nic['id'], self.api.tables[MODULES], 'FPGA scan cannot remove NIC inventory')
        self.assertEqual('FPGA-OLD', self.api.tables[ASSETS][asset['id']]['serial'])
        self.assertEqual(module['id'],self.api.tables[ASSETS][asset['id']]['module'])


if __name__ == '__main__':
    unittest.main()


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.sync=shared.Sync(dict(netbox_url='https://synthetic.invalid/netbox',netbox_token='synthetic',validate_certs=True),False)

    def test_delete_204_never_decodes_empty_json(self):
        response=Response(None,status_code=204)
        response.json=lambda: (_ for _ in ()).throw(ValueError('No JSON body'))
        with patch.object(self.sync.session,'request',return_value=response):
            self.assertIsNone(self.sync.request('DELETE','dcim/modules/1/'))

    def test_pagination_and_ambiguous_identity_on_later_page(self):
        pages=[Response({'count':2,'results':[{'id':1}],'next':'https://synthetic.invalid/netbox/api/dcim/modules/?offset=1'}),Response({'count':2,'results':[{'id':2}],'next':None})]
        with patch.object(self.sync.session,'request',side_effect=pages) as request:
            with self.assertRaisesRegex(ValueError,'Ambiguous'): self.sync.find(MODULES,serial='shared')
            self.assertEqual(2,request.call_count)

    def test_foreign_pagination_refused(self):
        with patch.object(self.sync.session,'request',return_value=Response({'results':[],'next':'https://foreign.invalid/api/'})) as request:
            with self.assertRaisesRegex(ValueError,'foreign'): self.sync.list(MODULES)
            self.assertEqual(1,request.call_count)


class GeneralInventoryTest(unittest.TestCase):
    setUp = LifecycleTest.setUp
    installed = LifecycleTest.installed
    def test_chassis_serial_identity_survives_hostname_change(self):
        dtype=self.api.add('dcim/device-types/',manufacturer=self.maker['id'],model='Chassis')
        self.api.tables['dcim/devices/'][self.device['id']]['device_type']=dtype['id']
        params=dict(self.params,mode='device',device='RENAMED',serial='CHASSIS-001',manufacturer='BittWare',model='Chassis')
        inventory.synchronize(params,False)
        self.assertEqual(1,len(self.api.rows('dcim/devices/')))
        self.assertEqual(self.device['id'],scalar(self.api.rows(ASSETS)[0]['device']))
        self.assertEqual('RENAMED',self.api.rows('dcim/devices/')[0]['name'])
        self.api.writes.clear();self.assertEqual([],inventory.synchronize(params,False));self.assertEqual([],self.api.writes)

    def test_component_repeat_replacement_and_scoped_removal(self):
        item=dict(name='DDR5 slot1',kind='DDR5',part='DIMM',serial='MEM-OLD')
        params=dict(self.params,mode='components',manufacturer='BittWare',items=[item])
        inventory.synchronize(params,False);asset=copy.deepcopy(self.api.rows(ASSETS)[0])
        self.api.writes.clear();self.assertEqual([],inventory.synchronize(params,False));self.assertEqual([],self.api.writes)
        inventory.synchronize(dict(params,items=[dict(item,serial='MEM-NEW')]),False)
        retained=self.api.tables[ASSETS][asset['id']]
        self.assertEqual('MEM-OLD',retained['serial']);self.assertIsNone(retained['inventoryitem']);self.assertEqual('stored',retained['status'])
        inventory.synchronize(dict(params,items=[],complete=False,scope=['DDR5']),False)
        self.assertEqual(1,len(self.api.rows('dcim/inventory-items/')))
        inventory.synchronize(dict(params,items=[],complete=True,scope=['NVMe']),False)
        self.assertEqual(1,len(self.api.rows('dcim/inventory-items/')))
        inventory.synchronize(dict(params,items=[],complete=True,scope=['DDR5']),False)
        self.assertEqual(1,len(self.api.rows('dcim/inventory-items/')))
        self.assertEqual(2,len(self.api.rows(ASSETS)))

    def test_nexus_exact_bay_scope_preserves_other_bays(self):
        old,asset=self.installed()
        item=dict(bay='Ethernet1/1',model='QSFP',manufacturer='BittWare',serial='QSFP-OLD')
        params=dict(self.params,mode='nexus',items=[item])
        inventory.synchronize(params,False)
        inventory.synchronize(dict(params,items=[],complete=True,scope=['Ethernet1/1']),False)
        self.assertIn(old['id'],self.api.tables[MODULES])
        self.assertEqual(2,len(self.api.rows(MODULES)))
        self.assertIsNotNone(next(a for a in self.api.rows(ASSETS) if a['serial']=='QSFP-OLD')['module'])


class FpgaParserTest(unittest.TestCase):
    def parse(self, text):
        return filters.cards(text, r'^\s*Index\s*:\s*(\d+)\b', r'^IA-860M\s+(\S+)\s*$',
            r'^\s*Part Number\s*:\s*(.+)$', r'^\s*Version\s*:\s*(.+)$',
            r'^\s*BMC Version\s*:\s*(.+)$', {})

    def test_each_sdk_index_needs_exactly_one_serial_record(self):
        good='IA-860M FPGA-0\n Index : 0\n Part Number : IA-860M\n BMC Version : 1\n'
        self.assertTrue(self.parse(good)['complete'])
        for malformed in (' Board missing serial\n Index : 1\n Part Number : IA-860M\n BMC Version : 1\n',
                          ' Index : invalid\n Part Number : IA-860M\n BMC Version : 1\n',
                          'IA-860M FPGA-1\n Part Number : IA-860M\n BMC Version : 1\n'):
            with self.subTest(record=malformed):
                with self.assertRaisesRegex(ValueError,'Incomplete FPGA'):self.parse(good+malformed)

    def test_placeholder_chassis_serials_are_rejected(self):
        for serial in ('', 'Default string', 'To Be Filled By O.E.M.', 'To Be Filled By OEM',
                       'Not Specified', 'System Serial Number', 'Chassis Serial Number'):
            with self.subTest(serial=serial):
                with self.assertRaisesRegex(ValueError,'Physical serial'):
                    shared.physical_serial(serial)
