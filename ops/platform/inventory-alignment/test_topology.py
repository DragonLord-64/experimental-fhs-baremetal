"""Topology ambiguity, conflict and parsing contracts; no network required."""
import unittest
from unittest.mock import patch
from test_importer import load, ROOT, modules, shared

with patch.dict('sys.modules', dict(modules, **{'ansible.module_utils.fhs_netbox': shared})):
    topology = load('topology', 'playbooks/netbox/library/fhs_topology_sync.py')
filters = load('topology_filters', 'playbooks/netbox/filter_plugins/fhs_topology.py')


class Fake:
    interfaces = {}
    def __init__(self, params, check):
        self.plan = []; self.check = check
    def find(self, path, **query):
        return dict(id=query['name'], name=query['name'])
    def list(self, path, **query):
        return self.interfaces.get(query['device_id'], [])
    def request(self, *args, **kwargs):
        raise AssertionError('Unexpected write or cable lookup')


class Topology(unittest.TestCase):
    def run_sync(self, observations):
        with patch.object(topology, 'Sync', Fake):
            return topology.synchronize(dict(observations=observations), True)
    def setUp(self):
        Fake.interfaces = {'switch': [dict(id=1, name='Ethernet1/1'), dict(id=2, name='Ethernet1/2')],
                           'host': [dict(id=3, name='C0-QSFP0')]}
    def observations(self, serial='DAC-1'):
        return [dict(device='switch', serials=[dict(port='Ethernet1/1', serial='DAC-1', kind='nexus')]),
                dict(device='host', serials=[dict(port='C0-QSFP0', serial=serial, kind='fpga')])]
    def test_exact_serial_and_preview(self):
        result = self.run_sync(self.observations())
        self.assertEqual(len(result['plan']), 1)
        self.assertEqual(result['plan'][0]['after']['a_terminations'][0]['object_id'], 3)
    def test_suffix_mismatch_preserved(self):
        self.assertEqual(self.run_sync(self.observations('DAC-2'))['plan'], [])
    def test_breakout_lanes_share_one_physical_cable(self):
        observations = self.observations()
        Fake.interfaces['switch'][0]['name'] = 'Ethernet1/1/1'
        Fake.interfaces['switch'][1]['name'] = 'Ethernet1/1/2'
        observations[0]['serials'][0]['port'] = 'Ethernet1/1/1'
        observations[0]['serials'].append(dict(port='Ethernet1/1/2', serial='DAC-1', kind='nexus'))
        plan = self.run_sync(observations)['plan']
        self.assertEqual(len(plan), 1)
        self.assertEqual(len(plan[0]['after']['b_terminations']), 2)
    def test_occupied_endpoint_preserved(self):
        Fake.interfaces['host'][0]['cable'] = dict(id=99)
        self.assertEqual(self.run_sync(self.observations())['plan'], [])
    def test_conflicting_lldp_and_serial_preserved(self):
        observations = self.observations()
        observations[1]['neighbors'] = [dict(local='C0-QSFP0', remote='switch', port='Ethernet1/2')]
        self.assertEqual(self.run_sync(observations)['plan'], [])
    def test_unidentified_fpga_serial_cannot_classify_a_dac(self):
        data = filters.topology_linux('host', {}, [], [dict(rc=0, item=dict(card_index=0),
            stdout='QSFP0:\n vendor_serial_number : SYN-CABLE-2\n')])
        self.assertEqual(data['serials'], [])
        self.assertEqual(data['ports'][0]['serial'], 'SYN-CABLE-2')
    def test_lldp_json(self):
        import json
        data = filters.topology_linux('host', dict(rc=0, stdout=json.dumps(dict(lldp=dict(interface=dict(
            eth0=dict(chassis={'switch': {}}, port=dict(id=dict(type='ifname', value='Ethernet1/1')))))))), [], [])
        self.assertEqual(data['neighbors'][0]['remote'], 'switch')

    def test_empty_lldp_reports_preservation(self):
        data = filters.topology_linux('host', dict(rc=0, stdout='{}'), [], [])
        self.assertEqual(data['neighbors'], [])
        self.assertIn('no neighbors', data['omissions'][0])

    def test_nexus_wrapped_lldp_schema_and_management_port(self):
        data = filters.topology_nexus('switch', {'__readonly__': {'TABLE_nbor_detail': {'ROW_nbor_detail': [
            dict(l_port_id='mgmt0', sys_name='host', port_id='946d.ae1f.6ae8'),
            dict(l_port_id='Eth1/1', sys_name='host', port_id='eth0')]}}}, {})
        self.assertEqual(data['interfaces'], ['mgmt0', 'Ethernet1/1'])
        self.assertEqual(data['neighbors'][0]['port'], '946d.ae1f.6ae8')
    def test_lldp_remote_mac_resolves_unique_interface(self):
        Fake.interfaces['host'][0]['primary_mac_address'] = dict(mac_address='94:6d:ae:1f:6a:e8')
        result = self.run_sync([dict(device='switch', neighbors=[dict(local='Ethernet1/1', remote='host', port='946d.ae1f.6ae8')])])
        self.assertEqual(len(result['plan']), 1)
    def test_lldp_list_shape_and_probe_failure_reported(self):
        import json
        neighbor = {'chassis': {'switch': {'id': {'type': 'mac', 'value': '00:01:02:03:04:05'}}},
                    'port': {'id': {'type': 'ifname', 'value': 'Eth1/1'}}}
        lldp = dict(rc=0, stdout=json.dumps({'lldp': {'interface': [{'eth0': [neighbor]}]}}))
        data = filters.topology_linux('host', lldp, [dict(rc=1, item=dict(interface='eth0'))], [])
        self.assertEqual(data['neighbors'][0]['port'], 'Ethernet1/1')
        self.assertIn('EEPROM probe failed', data['omissions'][0])


if __name__ == '__main__': unittest.main()
