"""Focused contracts for observed ports, exact DAC grouping and metadata safety."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from test_importer import load, modules, shared, NetBox

with patch.dict('sys.modules', dict(modules, **{'ansible.module_utils.fhs_netbox': shared})):
    topology = load('discovery_topology', 'playbooks/netbox/library/fhs_topology_sync.py')
    placement = load('discovery_placement', 'playbooks/netbox/library/fhs_placement_sync.py')
    schema = load('discovery_schema', 'playbooks/netbox/filter_plugins/fhs_placement.py')
    helpers = load('discovery_helpers', 'playbooks/netbox/module_utils/fhs_inventory_helpers.py')
filters = load('discovery_filters', 'playbooks/netbox/filter_plugins/fhs_topology.py')
FIXTURES = Path(__file__).parent/'fixtures/discovery'


class Discovery(unittest.TestCase):
    def test_qsfp_photo_clipping_and_official_removed_port(self):
        parsed = filters.qsfp_ports([dict(rc=0, item=dict(card_index=i), stdout=(FIXTURES/f).read_text())
            for i, f in enumerate(('qsfp-photo.txt', 'qsfp-official.txt'))])
        ports = parsed['ports']
        self.assertEqual(len(ports), 5)
        self.assertEqual([p['name'] for p in ports], ['C0-QSFP0','C0-QSFP1','C1-QSFP0','C1-QSFP1','C1-QSFP2'])
        self.assertEqual(ports[-1]['present'], False)
        self.assertEqual(ports[-1]['serial'], '')
        self.assertTrue(ports[0]['dac'])
        self.assertEqual(ports[0]['metadata']['techstr'], '850nm VCSEL')
        self.assertIsNone(ports[1]['present'])  # cropped in original, never filled in
        self.assertNotIn('techstr', ports[1]['metadata'])
        self.assertEqual(ports[2]['serial'].removesuffix('-1'), ports[3]['serial'].removesuffix('-2'))

    def test_unknown_vendor_part_is_not_a_dac_even_with_serial_or_techstr(self):
        self.assertFalse(filters.dac('UNKNOWN', 'QDD-400G-PC01'))
        self.assertFalse(filters.dac('FS', 'LOOKS-LIKE-DAC-COPPER'))
        text=(FIXTURES/'qsfp-photo.txt').read_text().replace('QDD-400G-PC01','QDD-400G-FR4')
        parsed=filters.topology_linux('SYN-HOST', {}, [], [dict(rc=0,item=dict(card_index=0),stdout=text)])
        self.assertEqual(parsed['serials'], [])
        self.assertEqual(len(parsed['ports']), 2)

    def test_all_seven_lldp_rows_and_port_formats_survive_nexus_parser(self):
        data=[filters.topology_nexus('SYN-NEXUS-'+label.upper(), (FIXTURES/f'nexus-{label}-lldp.json').read_text(),
            (FIXTURES/f'nexus-{label}-optics.json').read_text()) for label in ('a','b')]
        self.assertEqual([len(d['neighbors']) for d in data], [3,4])
        self.assertEqual(data[0]['neighbors'][1]['port'], '0200.0000.0001')
        self.assertEqual(data[1]['neighbors'][-1]['port'], 'ten-gigabitEthernet 1/0/27')
        self.assertEqual([s['connector'] for s in data[0]['serials'][:2]], ['Ethernet1/1']*2)

    def test_failed_and_empty_qsfp_probes_do_not_invent_fixed_ports(self):
        parsed=filters.qsfp_ports([dict(rc=1,item=dict(card_index=0)),dict(rc=0,stdout='',item=dict(card_index=1))])
        self.assertEqual(parsed['ports'], [])
        self.assertEqual(len(parsed['omissions']), 2)
        self.assertEqual(filters.observed_modules([dict(card_index=0)], [], 'other')[0]['interfaces'], [])

    def test_metadata_schema_accepts_independent_inlets_and_rejects_ambiguity(self):
        base=dict(site=' SYN ', role='Server', location='Room', rack='Rack', rack_unit=12,
            power_ports=[dict(name='PSU1',pdu_serial='SYN-PDU-A',pdu_port='12'),dict(name='PSU2',pdu_serial='SYN-PDU-B',pdu_port='8')])
        self.assertEqual(schema.server_metadata(base)['site'], 'SYN')
        class TaggedInteger(int):
            pass
        self.assertEqual(schema.server_metadata(dict(base, rack_unit=TaggedInteger(12)))['rack_unit'], 12)
        for bad in (0,-1,True,12.5,'12'):
            with self.subTest(unit=bad), self.assertRaises(ValueError): schema.server_metadata(dict(base,rack_unit=bad))
        for ports in ([base['power_ports'][0]]*2,[dict(name='PSU1',pdu_serial='SYN-PDU-A',pdu_port=12)]):
            with self.assertRaises(ValueError): schema.server_metadata(dict(base,power_ports=ports))


class Reconcile(unittest.TestCase):
    def setUp(self):
        self.api=NetBox()
        self.host=self.api.add('dcim/devices/',name='SYN-HOST',device_type=dict(u_height=2),rack=None)
        self.switch=self.api.add('dcim/devices/',name='SYN-SWITCH')
        self.pdu1=self.api.add('dcim/devices/',name='SYN-PDU-A',serial='SYN-PDU-A')
        self.pdu2=self.api.add('dcim/devices/',name='SYN-PDU-B',serial='SYN-PDU-B')
        for pdu,name in ((self.pdu1,'12'),(self.pdu2,'8')):
            self.api.add('dcim/power-outlets/',device=pdu['id'],name=name)
        site=self.api.add('dcim/sites/',name='SYN-SITE')
        self.rack=self.api.add('dcim/racks/',site=site['id'],name='SYN-RACK',u_height=42)
        self.meta=dict(site='SYN-SITE',rack='SYN-RACK',rack_unit=12,power_ports=[
            dict(name='PSU1',pdu_serial='SYN-PDU-A',pdu_port='12'),dict(name='PSU2',pdu_serial='SYN-PDU-B',pdu_port='8')])
        self.params=dict(netbox_url='https://synthetic.invalid',netbox_token='synthetic',validate_certs=True,device='SYN-HOST',metadata=self.meta)

    def apply(self,check=False,metadata=None):
        with patch.object(shared.requests,'Session',return_value=self.api):
            return placement.synchronize(dict(self.params,metadata=self.meta if metadata is None else metadata), check)

    def test_preview_no_writes_and_missing_metadata_preserves_everything(self):
        result=self.apply(True)
        self.assertEqual(len([p for p in result['plan'] if p['object'].endswith(' cable')]),2)
        self.assertEqual(self.api.writes,[])
        self.assertEqual(self.apply(metadata={})['plan'],[])

    def test_bad_second_inlet_refuses_before_first_write(self):
        self.meta['power_ports'][1]['pdu_serial']='missing'
        with self.assertRaisesRegex(ValueError,'missing or ambiguous'): self.apply()
        self.assertEqual(self.api.writes,[])

    def test_ambiguous_pdu_occupied_outlet_invalid_and_conflicting_placement(self):
        self.api.add('dcim/devices/',name='duplicate',serial='SYN-PDU-A')
        with self.assertRaisesRegex(ValueError,'ambiguous'): self.apply()
        self.api.tables['dcim/devices/'].pop(self.api.next_id-1)
        outlet=self.api.rows('dcim/power-outlets/')[0];outlet['mark_connected']=True
        with self.assertRaisesRegex(ValueError,'occupied'): self.apply()
        outlet.pop('mark_connected')
        for unit in (43,0,True):
            with self.assertRaises(ValueError): self.apply(metadata=dict(self.meta,rack_unit=unit))
        self.api.add('dcim/devices/',name='occupant',rack=self.rack['id'],position=13.5,device_type=dict(u_height=0.5))
        with self.assertRaisesRegex(ValueError,'overlaps'): self.apply()
        self.assertEqual(self.api.writes,[])

    def test_alias_resolution_and_multiple_physical_connectors_are_ambiguous(self):
        for device, names in ((self.host,['C0-QSFP0']), (self.switch,['Ethernet1/1/1','Ethernet1/1/2','Ethernet1/2'])):
            for name in names:self.api.add('dcim/interfaces/',device=device['id'],name=name)
        observations=[dict(device='SYN-HOST',identity=dict(aliases=['SYN-ACCESS']),serials=[dict(port='C0-QSFP0',serial='SYN-CABLE',kind='fpga')]),
            dict(device='SYN-SWITCH',serials=[dict(port=p,serial='SYN-CABLE',kind='nexus') for p in ['Ethernet1/1/1','Ethernet1/1/2']])]
        with patch.object(shared.requests,'Session',return_value=self.api):
            result=topology.synchronize(dict(self.params,observations=observations),True)
            self.assertEqual(len(result['plan']),1)
            self.assertEqual(sum(len(result['plan'][0]['after'][k]) for k in ('a_terminations','b_terminations')),3)
            observations[1]['serials'].append(dict(port='Ethernet1/2',serial='SYN-CABLE',kind='nexus'))
            self.assertEqual(topology.synchronize(dict(self.params,observations=observations),True)['plan'],[])


if __name__ == '__main__': unittest.main()
