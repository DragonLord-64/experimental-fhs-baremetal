"""Servers-only visual fixture acceptance; no synthetic sensor observations."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VisualFixture(unittest.TestCase):
    def test_inventory_partition_includes_missing_actual_hosts(self):
        servers = [p for p in load('exact').inventory() if p['kind'] == 'server']
        actual = {(p['unit'], p['fhs']) for p in servers if p['deployed']}
        visual = {(p['unit'], p['fhs']) for p in servers if not p['deployed']}
        self.assertEqual(132, len(servers))
        self.assertEqual(16, len(actual))
        self.assertEqual(116, len(visual))
        self.assertFalse(actual & visual)
        self.assertTrue({('FSPUnit1', f'FHS{i}') for i in range(1, 5)} <= actual)

    def test_every_visual_rack_server_consumes_provenance_metric(self):
        dashboards = load('generate').build()
        targets = {t['legendFormat']: t['expr']
                   for p in dashboards['rack']['panels'] for t in p.get('targets', [])}
        for host in load('exact').inventory():
            if host['kind'] != 'server' or host['deployed']:
                continue
            with self.subTest(host=host['id']):
                self.assertTrue(host['id'] in targets,
                              'Visual status must consume a feed, not a fixed green element')
                expr = targets[host['id']]
                self.assertIn('fhs_visual_status{', expr)
                self.assertIn('origin="visual_fixture"', expr)
                self.assertIn('unit="' + host['unit'] + '"', expr)
                self.assertIn('fhs="' + host['fhs'] + '"', expr)

    def test_fixture_context_visible_on_rack_and_server(self):
        dashboards = load('generate').build()
        for view in ('rack', 'fhs'):
            text = ' '.join(p.get('description', '') + ' ' +
                            p.get('options', {}).get('content', '')
                            for p in dashboards[view]['panels']).lower()
            with self.subTest(view=view):
                self.assertIn('visual fixture', text)
                self.assertIn('not observed', text)


    def test_feed_is_deterministic_status_only_and_matches_file(self):
        import sys
        sys.path.insert(0,str(ROOT))
        try:
            fixture=load('visual_fixture')
            rendered=fixture.render()
            self.assertEqual(rendered,(ROOT/'visual-status.prom').read_text())
            lines=[line for line in rendered.splitlines() if not line.startswith('#')]
            self.assertEqual(116,len(lines))
            self.assertEqual(116,len(set(lines)))
            self.assertTrue(all(line.startswith('fhs_visual_status{') and line.endswith('} 0') for line in lines))
            self.assertNotIn('up{',rendered)
        finally:
            sys.path.pop(0)

    def test_actual_queries_never_consume_fixture_and_readings_stay_observed(self):
        dashboards=load('generate').build()
        targets={t['legendFormat']: t['expr'] for p in dashboards['rack']['panels'] for t in p.get('targets',[])}
        for host in load('exact').inventory():
            if host['kind']=='server' and host['deployed']:
                self.assertNotIn('fhs_visual_status',targets[host['id']])
        for panel in dashboards['fhs']['panels']:
            if panel['title'].endswith(' · readings'):
                for target in panel['targets']:
                    self.assertNotIn('fhs_visual_status',target['expr'])
                    self.assertNotIn('or on() vector(0)',target['expr'])

    def test_patch_is_offline_guarded_and_only_writes_separate_key(self):
        import sys
        sys.path.insert(0, str(ROOT))
        try:
            fixture = load('visual_fixture')
            snapshot = {'kind':'ConfigMap', 'metadata':{'namespace':'fhs-emulators',
                        'name':'monitoring-fixtures', 'uid':'test-uid', 'resourceVersion':'42'},
                        'data':{'node.prom':'preserve actual data'}}
            patch = fixture.configmap_patch(snapshot)
            self.assertEqual(['test','test','add'], [p['op'] for p in patch])
            self.assertEqual('/data/visual-status.prom', patch[-1]['path'])
            self.assertEqual(fixture.render(), patch[-1]['value'])
            self.assertEqual('preserve actual data', snapshot['data']['node.prom'])
            snapshot['metadata']['namespace'] = 'production'
            with self.assertRaises(ValueError):
                fixture.configmap_patch(snapshot)
            snapshot['metadata']['namespace'] = 'fhs-emulators'
            del snapshot['metadata']['resourceVersion']
            with self.assertRaises(ValueError):
                fixture.configmap_patch(snapshot)
        finally:
            sys.path.pop(0)

    def test_live_gate_preserves_incomplete_actual_coverage_and_scenarios(self):
        import sys
        sys.path.insert(0, str(ROOT))
        try:
            gate = load('validate_visual_fixture')
            servers = [h for h in gate.inventory() if h['kind'] == 'server']
            feed = [{'metric': {'unit': h['unit'], 'fhs': h['fhs']},
                     'value': [0, '0']} for h in servers if not h['deployed']]
            responses = {'fhs_visual_status{job="node-emulator",origin="visual_fixture"}': feed}
            combined = {}
            for host in servers:
                unit, fhs = host['unit'], host['fhs']
                # VCCUnit1 has incomplete coverage; other actual healthy hosts
                # still use observed status, while the named scenarios stay strict.
                state = 3 if unit in ('FSPUnit1', 'VCCUnit1') else (1 if (unit, fhs) == ('FSPUnit2', 'FHS1') else 0)
                expr = gate.server_status(gate.health(unit, fhs), unit, fhs).replace('$job', 'fhs')
                responses[expr] = [{'value': [0, str(state)]}]
                combined[unit, fhs] = expr
                if host['deployed']:
                    observed = gate.inventory_fallback(gate.health(unit, fhs), gate.expected_host().replace('$unit', unit).replace('$fhs', fhs)).replace('$job', 'fhs')
                    self.assertNotIn('fhs_visual_status', observed)
                    responses[observed] = [{'value': [0, str(state)]}]
            self.assertEqual({'fixture_servers': 116, 'actual_servers': 16, 'status_queries': 132}, gate.validate(responses.__getitem__))
            for identity in [('VCCUnit1', 'FHS1'), ('FSPUnit1', 'FHS1'), ('FSPUnit2', 'FHS1'), ('FSPUnit4', 'FHS1')]:
                with self.subTest(identity=identity):
                    expr = combined[identity]
                    original = responses[expr]
                    responses[expr] = [{'value': [0, '0' if identity[0] != 'FSPUnit4' else '3']}]
                    with self.assertRaises(ValueError):
                        gate.validate(responses.__getitem__)
                    responses[expr] = original
        finally:
            sys.path.pop(0)
