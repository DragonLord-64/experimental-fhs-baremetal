"""Finite adapter checks using synthetic Bifrost data; no network or secrets."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('bifrost_adapter', ROOT/'playbooks/netbox/filter_plugins/bifrost_inventory.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


class AdapterTest(unittest.TestCase):
    def nodes(self):
        return {'legacy-key':dict(name='node-a',ipv4_address='192.0.2.10',driver_info=dict(redfish_address='https://192.0.2.20:443',redfish_username='fixture',redfish_password='synthetic-only')),
                'node-b':dict(ipv4_address='192.0.2.11',driver_info=dict(ipmi_address='192.0.2.21',ipmi_username='fixture',ipmi_password='synthetic-only',ipmi_port=9623))}

    def test_redfish_and_ipmi_with_alias_selection(self):
        a,b=module.bifrost_import_hosts(self.nodes())
        self.assertEqual(('node-a','192.0.2.10','192.0.2.20',623),(a['name'],a['ansible_host'],a['netbox_ipmi_address'],a['netbox_ipmi_port']))
        self.assertEqual(9623,b['netbox_ipmi_port'])
        self.assertEqual([a],module.bifrost_import_hosts(self.nodes(),['legacy-key']))
        self.assertNotIn('bootstrap_chassis_serial',a)

    def test_shared_defaults_and_per_node_override(self):
        nodes={'node':dict(ipv4_address='192.0.2.10',driver_info=dict(ipmi_address='192.0.2.20',ipmi_username='node-user'))}
        a=module.bifrost_import_hosts(nodes,driver_defaults=dict(ipmi_username='shared-user',ipmi_password='synthetic-only'))[0]
        self.assertEqual('node-user',a['netbox_ipmi_username'])

    def test_unknown_missing_and_duplicate_inputs_fail(self):
        with self.assertRaises(module.AnsibleFilterError):module.bifrost_import_hosts(self.nodes(),['not-present'])
        nodes=self.nodes();nodes['node-b']['ipv4_address']='192.0.2.10'
        with self.assertRaises(module.AnsibleFilterError):module.bifrost_import_hosts(nodes)
        nodes=self.nodes();nodes['legacy-key']['driver_info'].pop('redfish_password')
        with self.assertRaises(module.AnsibleFilterError):module.bifrost_import_hosts(nodes)


if __name__=='__main__':unittest.main()
