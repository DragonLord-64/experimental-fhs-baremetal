"""Reduced inventory must retain identities from the original full inventory."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from canonical_topology_reference import topology as original_topology
from topology import configured, topology
from render import render


def retained_reference():
    full = original_topology()
    units = {f'VCCUnit{i}' for i in range(1, 5)} | {f'FSPUnit{i}' for i in range(1, 4)}
    result = {key: value for key, value in full.items()
              if key not in ('units', 'hosts', 'switches', 'mesh_links')}
    for key in ('units', 'hosts', 'switches'):
        result[key] = [entry for entry in full[key]
                       if entry['name' if key == 'units' else 'unit'] in units]
    switches = {s['name'] for s in result['switches']}
    for switch in result['switches']:
        switch['links'] = [link for link in switch['links']
                           if link['kind'] == 'host' or link['neighbor']['name'] in switches]
    result['mesh_links'] = [edge for edge in full['mesh_links']
                            if edge['a_switch'] in switches and edge['b_switch'] in switches]
    return result


class ReducedContracts(unittest.TestCase):
    def test_full_reference_remains_unchanged(self):
        self.assertEqual(topology(24, 27), original_topology())

    def test_every_retained_identity_and_interface_matches_original(self):
        actual, expected = topology(4, 3), retained_reference()
        for key in ('units', 'hosts', 'switches', 'mesh_links'):
            with self.subTest(collection=key):
                self.assertEqual(actual[key], expected[key])

    def test_default_config_and_render_are_reduced_canonical_inventory(self):
        # Read the repository default regardless of an operator's environment override.
        with patch.dict('os.environ', {'EMULATOR_CONFIG': str(ROOT / 'config.json')}):
            actual = configured()
            rendered = render()
        self.assertEqual(actual, retained_reference())
        cm = next(item for item in rendered['items'] if item['kind'] == 'ConfigMap')
        self.assertEqual(json.loads(cm['data']['topology.json']), retained_reference())

    def test_reduced_counts_and_scenarios(self):
        t = topology(4, 3)
        self.assertEqual((len(t['hosts']), len(t['switches']), len(t['mesh_links'])), (16, 7, 12))
        self.assertEqual(sum(len(s['links']) for s in t['switches']), 56)
        self.assertEqual(sum(h['telemetry'] != 'missing' for h in t['hosts']), 12)
        self.assertEqual([h['name'] for h in t['hosts'] if h['telemetry'] == 'missing'],
                         [f'fspunit1-fhs{i}' for i in range(1, 5)])
        self.assertEqual([h['name'] for h in t['hosts'] if h['telemetry'] == 'psu1_fault'], ['fspunit2-fhs1'])
        down = [(s['name'], link['local_port'], link['neighbor']['name'], link['remote_port'])
                for s in t['switches'] for link in s['links'] if link['state'] != 'up']
        self.assertEqual(down, [('VCCUnit1-switch', 'eth1/1/3', 'FSPUnit3-switch', 'eth1/1/1'),
                                ('FSPUnit3-switch', 'eth1/1/1', 'VCCUnit1-switch', 'eth1/1/3')])
