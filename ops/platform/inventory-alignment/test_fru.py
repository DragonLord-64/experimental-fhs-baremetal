"""Anonymized FRU parsing, serial-safe import and actual Ansible discovery checks."""
import copy
import json
from pathlib import Path
import sys
import unittest

from test_importer import filters, inventory, ASSETS
import test_importer
from test_task_flow import SOURCE
import test_task_flow

FIXTURE = Path(__file__).parent / 'fixtures/fru.txt'


def discover(text=None, **kwargs):
    return filters.fru_identity(dict(rc=0, stdout=FIXTURE.read_text() if text is None else text), **kwargs)


class FruParsingTest(unittest.TestCase):
    def test_separate_chassis_board_and_product_with_sources(self):
        result = discover(facts=dict(system_vendor='To Be Filled By O.E.M.', product_name='Default string'))
        self.assertEqual(dict(serial='SYN-CHASSIS-001', manufacturer='BittWare', model='SYN-SERVER-PART'), result['identity'])
        self.assertEqual('SYN-PRODUCT-001', result['hardware_fields']['product_serial'])
        self.assertEqual('SYN-BOARD-001', result['hardware_fields']['motherboard_serial'])
        self.assertEqual('09-MAY-2025', result['hardware_fields']['product_name'])
        self.assertEqual('0.2.0.0.0', result['hardware_fields']['product_version'])
        self.assertEqual('GENOAD8UD-2T/X550', result['components'][0]['model'])
        self.assertEqual('', result['components'][0]['part'])
        self.assertEqual('ASRockRack', result['components'][0]['manufacturer'])
        self.assertEqual('ipmitool fru ID 0: Chassis Serial', result['sources']['serial'])
        self.assertNotIn('bios_version', result['hardware_fields'])
        self.assertNotIn('bmc_firmware', result['hardware_fields'])
        self.assertEqual(2, len(result['records']))
        self.assertEqual('SYN-PSU-001', result['records'][1]['fields']['Product Serial'])

    def test_valid_dmi_then_explicit_overrides_take_precedence(self):
        facts = dict(system_vendor='DMI vendor', product_name='DMI model', product_serial='DMI product',
                     board_vendor='DMI board vendor', board_name='DMI board', board_serial='DMI board serial')
        result = discover(facts=facts, chassis_probe=dict(rc=0, stdout='DMI chassis\n'))
        self.assertEqual(dict(serial='DMI chassis', manufacturer='DMI vendor', model='DMI model'), result['identity'])
        self.assertEqual('DMI product', result['hardware_fields']['product_serial'])
        self.assertEqual('DMI board serial', result['components'][0]['serial'])
        result = discover(facts=facts, overrides=dict(serial='Override chassis', manufacturer='Override vendor', model='Override model'))
        self.assertEqual(dict(serial='Override chassis', manufacturer='Override vendor', model='Override model'), result['identity'])
        self.assertEqual('bootstrap_chassis_serial', result['sources']['serial'])

    def test_missing_failed_and_partial_output_are_optional(self):
        for probe in (dict(rc=127), dict(rc=1, stdout=FIXTURE.read_text()), dict(msg='permission denied'), dict(rc=0, stdout='')):
            with self.subTest(probe=probe.get('rc')):
                result = filters.fru_identity(probe)
                self.assertEqual({}, result['identity'])
                self.assertEqual({}, result['hardware_fields'])
                self.assertEqual([], result['components'])
        result = discover('FRU Device Description : Builtin FRU Device (ID 0)\n Board Serial : SYN-BOARD\n Product Serial : SYN-PRODUCT\n')
        self.assertEqual({}, result['identity'])
        self.assertEqual([], result['components'])
        self.assertEqual('SYN-BOARD', result['hardware_fields']['motherboard_serial'])

    def test_placeholders_dates_and_no_cross_component_serial_fallback(self):
        for placeholder in ('To be filled by OEM', 'To Be Filled By O.E.M.', 'Default string', 'Unknown', '00000000'):
            result = discover('FRU Device Description : Builtin FRU Device (ID 0)\n Chassis Serial : '+placeholder+'\n Product Serial : SYN-PRODUCT\n Board Serial : SYN-BOARD\n')
            self.assertNotIn('serial', result['identity'])
        for date in ('09-MAY-2025', '2025-05-09', '09/05/2025'):
            self.assertEqual({}, discover(f'FRU Device Description : Builtin FRU Device (ID 0)\n Product Name : {date}\n Chassis Part Number : {date}\n')['identity'])

    def test_multiple_records_never_mix_or_guess_selected_fru(self):
        self.assertEqual({}, discover(fru_id='99')['identity'])
        selected = discover(fru_id='3')
        self.assertEqual('SYN-PSU-MODEL', selected['identity']['model'])
        self.assertNotIn('serial', selected['identity'])
        self.assertEqual([], selected['components'])
        duplicate = FIXTURE.read_text() + '\nFRU Device Description : Duplicate (ID 0)\n Chassis Serial : SYN-OTHER\n'
        self.assertEqual({}, discover(duplicate)['identity'])
        conflict = FIXTURE.read_text().replace(' Board Mfg Date', ' Chassis Serial : SYN-CONFLICT\n Board Mfg Date')
        self.assertNotIn('serial', discover(conflict)['identity'])

    def test_partial_metadata_merge_preserves_previous_fields_and_other_frus(self):
        previous = filters.identity_metadata(discover())
        original = copy.deepcopy(previous)
        partial = discover('FRU Device Description : Builtin FRU Device (ID 0)\n Product Version : 2\n')
        merged = filters.identity_metadata(partial, previous)
        self.assertEqual('SYN-CHASSIS-001', merged['fru_inventory']['0']['fields']['Chassis Serial'])
        self.assertEqual('2', merged['fru_inventory']['0']['fields']['Product Version'])
        self.assertEqual(original['fru_inventory']['3'], merged['fru_inventory']['3'])
        self.assertEqual(original['hardware_identity_sources']['serial'], merged['hardware_identity_sources']['serial'])
        self.assertEqual(original, previous)


class OptionalImportTest(unittest.TestCase):
    setUp = test_importer.LifecycleTest.setUp

    def params_for_device(self, **options):
        dtype = self.api.add('dcim/device-types/', manufacturer=self.maker['id'], model='Chassis')
        self.api.tables['dcim/devices/'][self.device['id']]['device_type'] = dtype['id']
        return dict(self.params, mode='device', serial='', manufacturer='BittWare', model='Chassis', allow_missing_serial=True, **options)

    def test_absent_serial_preserves_known_chassis_and_asset(self):
        params = self.params_for_device()
        inventory.synchronize(dict(params, serial='CHASSIS-001'), False)
        original = copy.deepcopy(self.api.rows(ASSETS))
        self.api.writes.clear()
        self.assertEqual([], inventory.synchronize(params, False))
        self.assertEqual('CHASSIS-001', self.api.rows('dcim/devices/')[0]['serial'])
        self.assertEqual(original, self.api.rows(ASSETS))
        self.assertEqual([], self.api.writes)

    def test_new_device_without_serial_has_no_fabricated_asset(self):
        params = self.params_for_device(device='NEW-SYNTHETIC')
        self.api.add('dcim/sites/', name='Synthetic')
        self.api.add('dcim/device-roles/', name='Server')
        params.update(site='Synthetic', role='Server')
        inventory.synchronize(params, False)
        new = next(d for d in self.api.rows('dcim/devices/') if d['name'] == params['device'])
        self.assertFalse(new.get('serial'))
        self.assertEqual([], self.api.rows(ASSETS))
        self.api.writes.clear()
        self.assertEqual([], inventory.synchronize(params, False))

    def test_board_model_and_observed_part_are_distinct_and_missing_part_preserves_known(self):
        raw = FIXTURE.read_text().replace(' Board Serial', ' Board Part Number : SYN-BOARD-PART\n Board Serial')
        params = dict(self.params, mode='components', manufacturer='ASRockRack', items=discover(raw)['components'])
        inventory.synchronize(params, False)
        board = self.api.rows('dcim/inventory-items/')[0]
        itype = self.api.rows('plugins/inventory/inventory-item-types/')[0]
        self.assertEqual('GENOAD8UD-2T/X550', itype['model'])
        self.assertEqual('SYN-BOARD-PART', itype['part_number'])
        self.assertEqual('SYN-BOARD-PART', board['part_id'])
        self.api.writes.clear()
        self.assertEqual([], inventory.synchronize(params, False))
        self.assertEqual([], inventory.synchronize(dict(params, items=discover()['components']), False))
        self.assertEqual('SYN-BOARD-PART', board['part_id'])
        self.assertEqual([], self.api.writes)

    def test_motherboard_uses_board_vendor_and_keeps_asset_on_partial_discovery(self):
        result = discover()
        params = dict(self.params, mode='components', manufacturer='Unknown', items=result['components'], complete=False)
        inventory.synchronize(params, False)
        board = self.api.rows('dcim/inventory-items/')[0]
        vendor = next(v for v in self.api.rows('dcim/manufacturers/') if v['name'] == 'ASRockRack')
        self.assertEqual(vendor['id'], board['manufacturer'])
        self.assertEqual('SYN-BOARD-001', board['serial'])
        self.assertEqual('CHASSIS-001', self.api.rows('dcim/devices/')[0]['serial'])
        original = copy.deepcopy(self.api.rows(ASSETS))
        inventory.synchronize(dict(params, items=[]), False)
        self.assertEqual([board], self.api.rows('dcim/inventory-items/'))
        self.assertEqual(original, self.api.rows(ASSETS))
        self.api.writes.clear()
        self.assertEqual([], inventory.synchronize(params, False))


class FruTaskTest(unittest.TestCase):
    setUpClass = classmethod(test_task_flow.TaskFlowTest.setUpClass.__func__)
    setUp = test_task_flow.TaskFlowTest.setUp
    stop_server = test_task_flow.TaskFlowTest.stop_server
    run_tasks = test_task_flow.TaskFlowTest.run_tasks

    def test_complete_disk_memory_scope_cannot_remove_motherboard(self):
        import yaml
        board = self.api.add('dcim/inventory-items/', device=self.device['id'], name='Motherboard',
                             serial='SYN-BOARD', part_id='SYN-BOARD-MODEL', manufacturer=self.maker['id'],
                             description='FHS managed Motherboard')
        asset = self.api.add(ASSETS, serial='SYN-BOARD', inventoryitem_type=999,
                             inventoryitem=board['id'], status='used')
        task = next(t for parent in yaml.safe_load((SOURCE / 'tasks/apply.yml').read_text())
                    for t in parent.get('block', []) if t.get('name') == 'Reconcile serial-bearing DDR5 and NVMe assets')
        self.run_tasks([task], dict(facts=dict(self.vars['facts'], hostname='old-server'),
            bootstrap_components_complete=True, components_scan_complete=True,
            bootstrap_component_scope=['DDR5', 'NVMe', 'Motherboard']))
        self.assertEqual(board, self.api.tables['dcim/inventory-items/'][board['id']])
        self.assertEqual(asset, self.api.tables[ASSETS][asset['id']])
        self.assertFalse(any(method == 'DELETE' for method, *_ in self.api.writes))

    def test_actual_optional_discovery_commands_and_filter_in_check_mode(self):
        folder = self.folder / 'bin'; folder.mkdir()
        for command, output in [('ipmitool', FIXTURE.read_text()), ('cat', 'To Be Filled By O.E.M.\n')]:
            script = folder / command
            script.write_text('#!' + sys.executable + '\nprint(' + repr(output) + ')\n')
            script.chmod(0o700)
        tasks = [{'ansible.builtin.import_tasks': str(SOURCE / 'tasks/identity.yml')},
                 {'ansible.builtin.assert': {'that': [
                     'system_identity.identity.serial == "SYN-CHASSIS-001"',
                     'system_identity.identity.model == "SYN-SERVER-PART"',
                     'hardware_fields.product_serial == "SYN-PRODUCT-001"',
                     'discovered_components[0].serial == "SYN-BOARD-001"',
                     'not components_scan_complete']}}]
        variables = dict(hardware_simulation=True, bootstrap_chassis_serial="", hardware_command_path=str(folder),
                         facts=dict(hostname='synthetic', system_vendor='To be filled by OEM'), components_scan_complete=False)
        self.run_tasks(tasks, variables, check=True)
        (folder / 'ipmitool').write_text('#!' + sys.executable + '\nimport sys\nsys.exit(1)\n')
        tasks[1]['ansible.builtin.assert']['that'] = ['system_identity.identity == {}', 'discovered_components == []', 'hardware_fields == {}']
        self.run_tasks(tasks, variables, check=True)
        (folder / 'ipmitool').unlink()  # Missing binary also remains optional.
        self.run_tasks(tasks, variables, check=True)
        self.assertEqual([], self.api.writes)
