"""Exact authorized population regressions; synthetic snapshots only."""
import copy
import unittest

from test_prune import fixture
import prune
from inventory import LabError, PREFIX


def full_population():
    return fixture()


class ExactPopulationTests(unittest.TestCase):
    def test_complete_population_selects_exactly_160_obsolete(self):
        state, topology = full_population()
        result = prune.plan(state, topology)
        self.assertEqual(result['obsolete_logical'], 160)
        self.assertEqual(len(result['retained']), 23)

    def test_missing_retained_device_rejects_plan(self):
        state, topology = full_population()
        state[prune.TABLES[0]] = [row for row in state[prune.TABLES[0]]
                                 if row['name'] != PREFIX + 'vccunit1-fhs1']
        with self.assertRaises(LabError):
            prune.plan(state, topology)

    def test_incomplete_obsolete_selection_rejects_plan(self):
        state, topology = full_population()
        missing = next(row for row in state[prune.TABLES[0]]
                       if row['name'] == PREFIX + 'vccunit24-switch')
        state[prune.TABLES[0]].remove(missing)
        state['dependency_evidence']['device_ids'].remove(missing['id'])
        with self.assertRaises(LabError):
            prune.plan(state, topology)

    def test_retained_drift_fails_without_repair(self):
        mutations = (
            ('device', 'tags', []), ('device', 'serial', 'changed'),
            ('device', 'oob_ip', {'id': 999}),
            ('device', 'custom_fields', {'fhs_lab': {'kind': 'logical'}}),
            ('port', 'mgmt_only', False), ('ip', 'address', '203.0.113.250/32'),
            ('mac', 'mac_address', '02:ff:00:00:00:00'))
        for kind, field, value in mutations:
            state, topology = fixture()
            baseline = topology['retained_snapshot']
            table = {'device': 0, 'port': 1, 'ip': 2, 'mac': 3}[kind]
            expected = next((r for r in baseline[prune.TABLES[table]]
                             if kind != 'port' or r['name'] == 'bmc0'))
            row = next(r for r in state[prune.TABLES[table]] if r['id'] == expected['id'])
            row[field] = value
            before = copy.deepcopy(state)
            with self.subTest(kind=kind, field=field), self.assertRaises(LabError):
                prune.plan(state, topology)
            self.assertEqual(state, before)

    def test_canonical_evidence_is_required_and_must_include_bmc_defaults(self):
        for mutation in ('missing', 'renumbered', 'missing-bmc', 'unowned'):
            state, topology = fixture()
            baseline = topology['retained_snapshot']
            if mutation == 'missing':
                del topology['retained_snapshot']
            elif mutation == 'renumbered':
                baseline[prune.TABLES[2]][1]['address'] = '203.0.113.250/32'
            elif mutation == 'missing-bmc':
                baseline[prune.TABLES[1]] = [r for r in baseline[prune.TABLES[1]] if r['name'] != 'bmc0']
            else:
                baseline[prune.TABLES[0]][0]['tags'] = []
            with self.subTest(mutation=mutation), self.assertRaises(LabError):
                prune.plan(state, topology)
