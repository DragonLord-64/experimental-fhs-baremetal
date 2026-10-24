"""Acceptance regressions for the authorized dashboard refinements."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Refinements(unittest.TestCase):
    def test_one_u_devices_and_one_gap_between_unit_blocks(self):
        items = load('exact').inventory()
        for rack in range(1, 10):
            devices = sorted((p for p in items if p['rack'] == rack),
                             key=lambda p: p['position_u'])
            with self.subTest(rack=rack):
                self.assertTrue(all(p['height_u'] == 1 for p in devices))
                for previous, current in zip(devices, devices[1:]):
                    gap = current['position_u'] - (previous['position_u'] + previous['height_u'])
                    self.assertEqual(int(previous['unit'] != current['unit']), gap)
                self.assertEqual(29 if rack <= 6 else 17,
                                 devices[-1]['position_u'] + devices[-1]['height_u'] - devices[0]['position_u'])

    def test_detail_status_vocabulary_and_inventory_distinction(self):
        dashboards = load('generate').build()
        panels = [next(p for p in dashboards['fhs']['panels'] if p['title'] == 'Overall hardware health'),
                  next(p for p in dashboards['interface']['panels'] if p['title'] == 'Interface operational state')]
        for panel in panels:
            with self.subTest(panel=panel['title']):
                values = next(m['options'] for m in panel['fieldConfig']['defaults']['mappings']
                              if m['type'] == 'value')
                self.assertEqual('unknown', values['3']['text'])
                self.assertEqual('not deployed', values['4']['text'])
                self.assertTrue({v['text'] for v in values.values()} <=
                                {'ok', 'degraded', 'fault', 'unknown', 'not deployed'})


    def test_parent_hardware_and_shared_optics_do_not_depend_on_lane(self):
        dashboard = load('generate').build()['switch']
        board = next(p for p in dashboard['panels'] if p['type'] == 'canvas')
        parents = [e for e in board['options']['root']['elements']
                   if ' L' not in e['name'] and e['name'].endswith('health')]
        self.assertEqual(32, len(parents))
        self.assertTrue(all(e['config']['text']['mode'] == 'field' for e in parents))
        self.assertTrue(all(e['config']['text']['field'] == 'Parent inventory state' for e in parents))
        parent = next(t for t in board['targets'] if t['legendFormat'] == 'Parent inventory state')
        exact = load('exact')
        self.assertEqual(exact.parent_inventory_state(), parent['expr'])
        self.assertNotIn('nexus_', parent['expr'])
        self.assertNotIn('interface', parent['expr'])
        deployed = [p['id'] for p in exact.inventory() if p['kind'] == 'switch' and p['deployed']]
        self.assertEqual(7, len(deployed))
        self.assertIn('FSPUnit3-switch', deployed)
        self.assertNotIn('FSPUnit4-switch', deployed)
        overrides = next(o for o in board['fieldConfig']['overrides']
                         if o['matcher']['options'] == 'Parent inventory state')
        values = overrides['properties'][0]['value'][0]['options']
        self.assertEqual('unknown', values['3']['text'])
        self.assertEqual('not deployed', values['4']['text'])
        optics = [p for p in dashboard['panels'] if p['title'] in
                  ('Transceiver identity / status', 'Optic temperature', 'Optic voltage', 'RX / TX optical power')]
        self.assertEqual(4, len(optics))
        for panel in optics:
            self.assertEqual('vector(0) == 1', panel['targets'][0]['expr'])
            self.assertNotIn('operSt', panel['targets'][0]['expr'])
        self.assertTrue(any('link down' in p.get('options', {}).get('content', '') for p in dashboard['panels']))

    def test_observed_mesh_throughput_uses_native_directional_counter_rates(self):
        dashboard = load('generate').build()['mesh']
        throughput = [p for p in dashboard['panels']
                      if 'throughput' in p['title'].lower()]
        self.assertTrue(throughput)
        expressions = ' '.join(t['expr'] for p in throughput for t in p['targets'])
        # Sanitized actual contract: 112 counters / 112 valid rates, RX and TX
        # distinguished by dn suffix; each observed direction was 1016.949... B/s.
        self.assertIn('rate(nexus_interfaces_octets{', expressions)
        self.assertIn('[5m]', expressions)
        self.assertIn('dn', expressions)
        self.assertIn('dbgIfHC', expressions)
        self.assertIn('$switch_job', expressions)
        self.assertNotIn('operSt', expressions)  # link down must not erase rates
        self.assertNotIn('or vector(0)', expressions)
        self.assertNotIn('or on() vector(0)', expressions)
        self.assertRegex(expressions, r'8(?:\.0)?\s*/\s*(?:1e9|1000000000)')
        for panel in throughput:
            defaults = panel['fieldConfig']['defaults']
            self.assertEqual('unknown', defaults['noValue'])
            self.assertGreaterEqual(defaults.get('decimals', 0), 6)
        content = ' '.join(p.get('description', '') + ' ' +
                           p.get('options', {}).get('content', '') + ' ' + p['title']
                           for p in dashboard['panels'])
        self.assertNotIn('Rates are unavailable', content)
        capacity = next(p for p in dashboard['panels'] if p['title'] == 'Link capacity · Gbit/s')
        self.assertEqual('vector(0) == 1', capacity['targets'][0]['expr'])
        self.assertEqual('unknown', capacity['fieldConfig']['defaults']['noValue'])

    def test_switch_lane_identity_is_visible_separately_from_status(self):
        dashboard = load('generate').build()['switch']
        board = next(p for p in dashboard['panels'] if p['type'] == 'canvas')
        elements = board['options']['root']['elements']
        for port in range(1, 33):
            for lane in range(1, 5):
                with self.subTest(port=port, lane=lane):
                    slot = [e for e in elements if e['name'].startswith(f'P{port} L{lane} ')]
                    identity = [e for e in slot if e['config']['text']['mode'] == 'fixed'
                                and e['config']['text'].get('fixed') in
                                (str(lane), f'L{lane}', f'eth1/{port}/{lane}')]
                    self.assertTrue(identity, 'Each lane needs readable identity independent of its mapped status')

    def test_all_actual_host_component_selections_are_enumerated(self):
        import sys
        sys.path.insert(0, str(ROOT))
        plan = load('evidence_plan').build()
        self.assertEqual(336, plan['selection_count'])
        self.assertEqual(336, len({(s['host'], s['component']) for s in plan['selections']}))
        self.assertEqual(84, sum(s['unit'] == 'FSPUnit1' for s in plan['selections']))
        for selection in plan['selections']:
            self.assertTrue(selection['reading_queries'])
            self.assertIn('unit="'+selection['unit']+'"', selection['status_query'])
            self.assertIn('and on(job,instance)', selection['reading_queries'][0])

    def test_markdown_navigation_preserves_native_query_parameters(self):
        import re
        from urllib.parse import urlsplit, parse_qs
        g = load('generate')
        dashboards = g.build()
        content = dashboards['mesh']['panels'][-1]['options']['content']
        url = re.search(r'\]\((.*?)\)', content)[1]
        self.assertEqual(g.url('switch', dynamic={'switch': 'VCCUnit${vccu}-switch',
                                                 'unit': 'VCCUnit${vccu}'}), url)
        params = parse_qs(urlsplit(url).query)
        self.assertEqual(['VCCUnit${vccu}-switch'], params['var-switch'])
        self.assertEqual(['${ds:percentencode}'], params['var-ds'])
        self.assertIn('&${__url_time_range}', url)

    def test_dynamic_headers_use_display_text_and_compound_identity_mapping(self):
        dashboards = load('generate').build()
        self.assertIn('${unit:text} / ${fhs:text}', dashboards['fhs']['panels'][0]['options']['content'])
        self.assertIn('${switch:text}', dashboards['switch']['panels'][0]['options']['content'])
        table = next(p for p in dashboards['interface']['panels'] if p['type'] == 'table')
        mappings = table['fieldConfig']['defaults']['mappings']
        self.assertTrue(any(m.get('options', {}).get('result', {}).get('text') == 'fspu$1-fhs$2'
                            for m in mappings))

    def test_mesh_compact_status_encoding(self):
        dashboard = load('generate').build()['mesh']
        matrix = next(p for p in dashboard['panels'] if p['type'] == 'canvas')
        cells = [e for e in matrix['options']['root']['elements']
                 if e['name'].startswith('VCCU') and ' FSPU' in e['name']]
        self.assertEqual(648, len(cells))
        self.assertTrue(all(e['config']['text']['fixed'] == 'ND' for e in cells
                            if e['config']['text']['mode'] == 'fixed'))
        self.assertIn('ND = **not deployed**', dashboard['panels'][0]['options']['content'])
        self.assertIn('? = **unknown**', dashboard['panels'][0]['options']['content'])

    def test_compact_parent_and_lane_presentation_keeps_full_drilldown(self):
        from urllib.parse import urlsplit, parse_qs
        dashboard = load('generate').build()['switch']
        board = next(p for p in dashboard['panels'] if p['type'] == 'canvas')
        for e in board['options']['root']['elements']:
            if e['name'].endswith('health'):
                self.assertEqual('#ffffff', e['config']['color']['fixed'])
                self.assertGreaterEqual(e['placement']['width'], 64)
            if ' L' in e['name']:
                port = int(e['name'].split()[0][1:])
                lane = int(e['name'].split()[1][1:])
                params = parse_qs(urlsplit(e['links'][0]['url']).query)
                self.assertEqual([f'eth1/{port}/{lane}'], params['var-interface'])
                self.assertEqual([str(port)], params['var-port'])
                self.assertEqual(['${switch:percentencode}'], params['var-switch'])
                self.assertEqual(['${ds:percentencode}'], params['var-ds'])
                self.assertIn('${__url_time_range}', e['links'][0]['url'])
        self.assertIn('**not deployed**', dashboard['panels'][0]['options']['content'])
        self.assertIn('**unknown**', dashboard['panels'][0]['options']['content'])

    def test_peer_navigation_uses_opposite_raw_endpoint_and_preserves_context(self):
        from urllib.parse import urlsplit, parse_qs
        dashboard = load('generate').build()['interface']
        peer = next(p for p in dashboard['panels'] if p['title'] == 'Last-known peer')
        url = peer['fieldConfig']['defaults']['links'][0]['url']
        params = parse_qs(urlsplit(url).query)
        self.assertEqual(['${__data.fields.peer_role:percentencode}Unit${__data.fields.peer_number:percentencode}-switch'], params['var-switch'])
        self.assertEqual(['${__data.fields.portIdV:percentencode}'], params['var-interface'])
        self.assertEqual(['${__data.fields.peer_role:percentencode}Unit${__data.fields.peer_number:percentencode}'], params['var-unit'])
        self.assertEqual(['${ds:percentencode}'], params['var-ds'])
        self.assertIn('${__url_time_range}', url)
