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
