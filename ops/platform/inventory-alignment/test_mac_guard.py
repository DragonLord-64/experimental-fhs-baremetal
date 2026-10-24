"""Execute fleet MAC filtering and its guard from the actual task expressions."""
from pathlib import Path
import unittest

from jinja2.nativetypes import NativeEnvironment
import yaml

ROOT = Path(__file__).resolve().parents[3]


def flatten(values):
    result = []
    for value in values:
        result.extend(flatten(value) if isinstance(value, (tuple, list)) else [value])
    return result


def extract(key, container, field=None):
    value = container[key]
    if field is not None:
        for element in field if isinstance(field, list) else [field]:
            value = value[element]
    return value


class FleetMacGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tasks = yaml.safe_load((ROOT / 'playbooks/netbox/tasks/compare.yml').read_text())[0]['block']
        cls.task = next(t for t in tasks if t.get('name') == 'Reject ambiguous device names and duplicate discovery identities')
        cls.env = NativeEnvironment()
        # Ansible's unique filter materializes a list (Jinja's yields a generator).
        cls.env.filters.update(extract=extract, flatten=flatten, unique=lambda values: list(dict.fromkeys(values)))

    def fleet_and_guard(self, *macs):
        context = {'ansible_play_hosts': ['host-a', 'host-b'], 'hostvars': {
            host: {'discovered_interfaces': [{'name': 'eth0', 'mac': macs[index], 'addresses': []}]}
            for index, host in enumerate(('host-a', 'host-b'))}}
        fleet = self.env.from_string(self.task['vars']['fleet_macs']).render(**context)
        # Evaluate the assertion used by Ansible, not a duplicate Python policy.
        expression = next(e for e in self.task['ansible.builtin.assert']['that'] if e.startswith('fleet_macs '))
        return fleet, self.env.compile_expression(expression)(fleet_macs=fleet)

    def test_shared_placeholder_macs_do_not_block_inventory(self):
        for sentinel in ('', '00:00:00:00:00:00', '00:00:00:00', 'ee:ee:ee:ee:ee:ee'):
            with self.subTest(sentinel=sentinel):
                fleet, allowed = self.fleet_and_guard(sentinel, sentinel)
                self.assertEqual([], fleet)
                self.assertTrue(allowed)

    def test_ownership_reads_and_writes_use_same_sentinel_policy(self):
        for path in ('compare.yml','apply.yml'):
            tasks=yaml.safe_load((ROOT/'playbooks/netbox/tasks'/path).read_text())
            selected=[]
            def visit(entries):
                for task in entries:
                    if 'block' in task: visit(task['block'])
                    if task.get('name') in ('Read ownership of desired MAC addresses','Ensure MAC objects (NetBox 4.2+)','Set interface primary MACs'): selected.append(task)
            visit(tasks)
            self.assertTrue(selected)
            for task in selected:
                guard=self.env.compile_expression(task['when'])
                for mac in ('','00:00:00:00:00:00','00:00:00:00','ee:ee:ee:ee:ee:ee','EE:EE:EE:EE:EE:EE'):
                    self.assertFalse(guard(item={'mac':mac}),task['name'])
                self.assertTrue(guard(item={'mac':'02:11:22:33:44:55'}))

    def test_shared_real_mac_still_blocks_inventory(self):
        fleet, allowed = self.fleet_and_guard('02:11:22:33:44:55', '02:11:22:33:44:55')
        self.assertEqual(2, len(fleet))
        self.assertFalse(allowed)

    def test_valid_macs_remain_in_fleet(self):
        fleet, allowed = self.fleet_and_guard('02:11:22:33:44:55', '02:aa:bb:cc:dd:ee')
        self.assertEqual(['02:11:22:33:44:55', '02:aa:bb:cc:dd:ee'], fleet)
        self.assertTrue(allowed)


if __name__ == '__main__':
    unittest.main()
