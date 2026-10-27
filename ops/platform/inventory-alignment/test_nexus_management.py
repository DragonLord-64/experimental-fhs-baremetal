"""Focused management observations and native shared-client ownership contracts."""
import ipaddress
import unittest
from unittest.mock import patch
from test_importer import load, shared, NetBox, ROOT

management = load('nexus_management_test', 'playbooks/netbox/module_utils/fhs_nexus_management.py')


class Management(unittest.TestCase):
    def setUp(self):
        self.api = NetBox()
        self.device = self.api.add('dcim/devices/', name='SYN-MGMT', serial='SYN-MGMT')
        self.sync = shared.Sync(dict(netbox_url='http://fixture', netbox_token='synthetic', validate_certs=True), False)
        self.sync.session = self.api

    def observation(self, address='192.0.2.7/24'):
        fixture = (ROOT / 'ops/platform/inventory-alignment/fixtures/nexus-management/mgmt0.txt').read_text()
        return management.observe(fixture.replace('192.0.2.7/24', address))

    def run_sync(self, observation=None, ips=True):
        # The REST fixture's generic exact matcher lacks NetBox's host-IP filter.
        request = self.api.request
        def filtered(method, url, **kwargs):
            params = kwargs.get('params', {})
            if method == 'GET' and '/ipam/ip-addresses/' in url and 'address' in params:
                kwargs['params'] = {k: v for k, v in params.items() if k != 'address'}
                response = request(method, url, **kwargs)
                response.data['results'] = [r for r in response.data['results'] if
                    str(ipaddress.ip_interface(r['address']).ip) == params['address']]
                return response
            return request(method, url, **kwargs)
        with patch.object(self.api, 'request', filtered):
            return management.reconcile(self.sync, self.device, observation or self.observation(), ips)

    def test_apply_repeat_and_ipv6(self):
        self.run_sync()
        self.assertEqual(self.api.rows('ipam/ip-addresses/')[0]['address'], '192.0.2.7/24')
        self.assertEqual(self.api.rows('dcim/interfaces/')[0]['name'], 'mgmt0')
        self.assertIn('primary_ip4', self.api.rows('dcim/devices/')[0])
        self.api.writes.clear()
        self.run_sync()
        self.assertEqual(self.api.writes, [])
        self.run_sync(self.observation('2001:db8::7/64'))
        self.assertIn('primary_ip6', self.api.rows('dcim/devices/')[0])

    def test_failed_missing_and_ambiguous_preserve(self):
        for text in ('', '% Invalid command', 'mgmt0 is up\n Internet Address is 192.0.2.1',
                     'mgmt0 is up\n Internet Address is 192.0.2.1/24\n Internet Address is 192.0.2.2/24'):
            observation = management.observe(text)
            self.assertTrue(observation['diagnostics'])
            self.run_sync(observation)
            self.assertEqual(self.api.writes, [])

    def test_conflicting_owner_preflight(self):
        self.api.add('ipam/ip-addresses/', address='192.0.2.7/25', assigned_object_type='dcim.interface', assigned_object_id=99)
        self.assertIn('Conflicting', ' '.join(self.run_sync()))
        self.assertEqual(self.api.writes, [])

    def test_preview_and_interface_only(self):
        self.sync.check = True
        self.run_sync()
        self.assertTrue(self.sync.plan)
        self.assertEqual(self.api.writes, [])
        self.sync.check = False
        self.sync.cache.clear()
        self.run_sync(ips=False)
        self.assertEqual(len(self.api.rows('dcim/interfaces/')), 1)
        self.assertEqual(self.api.rows('ipam/ip-addresses/'), [])


if __name__ == '__main__':
    unittest.main()
