"""Portable offline contracts. Run directly; no checkout imports or containers."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((Path(__file__).with_name('native-layouts.json')).read_text())


def layout_digest(dashboard):
    # Freeze native geometry, allowing explicit demo provenance/status adapters.
    panels = []
    for panel in dashboard['panels']:
        panels.append({
            'id': panel.get('id'), 'type': panel['type'],
            'gridPos': panel['gridPos'],
            'elements': [
                {key: element.get(key) for key in ('name', 'type', 'placement', 'constraint')}
                for element in panel.get('options', {}).get('root', {}).get('elements', [])
            ],
        })
    return hashlib.sha256(json.dumps(panels, sort_keys=True).encode()).hexdigest()


class PortableDemo(unittest.TestCase):
    def test_required_launch_inputs(self):
        for name in ('compose.yaml', 'launch.sh', 'README.md', 'scenarios.json'):
            with self.subTest(path=name):
                self.assertTrue((ROOT / name).is_file(), f'Missing portable input: {name}')
        launch = ROOT / 'launch.sh'
        self.assertTrue(launch.exists() and launch.stat().st_mode & 0o111,
                        'launch.sh must be executable')

    def test_six_native_layouts_and_navigation(self):
        dashboards = {}
        for path in ROOT.rglob('*.json'):
            if 'tests' in path.relative_to(ROOT).parts:
                continue
            try:
                data = json.loads(path.read_text())
            except (ValueError, UnicodeError):
                continue
            if isinstance(data, dict) and 'panels' in data and 'uid' in data:
                self.assertNotIn(data['uid'], dashboards, 'Duplicate dashboard UID')
                dashboards[data['uid']] = data
        self.assertEqual(set(BASELINE), set(dashboards), 'Provision all six native dashboards')
        for uid, expected in BASELINE.items():
            with self.subTest(uid=uid):
                dashboard = dashboards[uid]
                self.assertEqual(expected['title'], dashboard['title'])
                self.assertEqual(expected['layout_sha256'], layout_digest(dashboard))
                self.assertEqual(expected['links'], dashboard['links'])
                selectors = {v['name']: v for v in dashboard['templating']['list']}
                for name, selected in expected['destinations'].items():
                    self.assertEqual(selected, selectors[name]['current'])

    def test_demo_population_summary(self):
        dashboard = json.loads((ROOT / 'grafana/dashboards/fhs.json').read_text())
        panels = {panel['id']: panel for panel in dashboard['panels']}
        for panel_id, title, expr in (
            (4, 'Configured FHS', 'count(demo_server_status)'),
            (5, 'Missing telemetry', 'count(demo_server_status == 3) or vector(0)'),
        ):
            self.assertEqual(panels[panel_id]['title'], title)
            self.assertEqual(panels[panel_id]['targets'][0]['expr'], expr)

    def test_numeric_fields_and_mock_query_contract(self):
        dashboards = {p.stem: json.loads(p.read_text()) for p in (ROOT/'grafana/dashboards').glob('*.json')}
        for name, dashboard in dashboards.items():
            for panel in dashboard['panels']:
                exprs = [t.get('expr','') for t in panel.get('targets',[])]
                self.assertNotIn('nexus_interfaces_octets', str(exprs))
                self.assertNotIn('rate(', str(exprs))
                self.assertNotIn('unavailable', panel.get('title',''))
                self.assertNotIn('observed', panel.get('title','').lower())
                if panel['type'] == 'stat' and not any('_status' in e and 'count(' not in e for e in exprs):
                    fields = panel['fieldConfig']['defaults']
                    self.assertNotIn('thresholds', fields, (name,panel['id']))
                    self.assertFalse(any(m['type']=='value' for m in fields.get('mappings',[])), (name,panel['id']))
                    self.assertEqual('fixed', fields['color']['mode'])
        mesh = {p['id']:p for p in dashboards['mesh']['panels']}
        for panel_id, status in [(2,0),(3,2),(4,3),(5,4)]:
            self.assertEqual(f'count(demo_mesh_status == {status}) or vector(0)',mesh[panel_id]['targets'][0]['expr'])
        switch = {p['id']:p for p in dashboards['switch']['panels']}
        for panel_id,unit in [(5,'celsius'),(6,'volt'),(7,'dBm')]:
            self.assertEqual(unit,switch[panel_id]['fieldConfig']['defaults']['unit'])
        self.assertEqual('count(demo_vlan_translation{vlan="$vlan"}) or vector(0)',dashboards['vlan']['panels'][4]['targets'][0]['expr'])

    def test_no_links_outside_portable_folder(self):
        for path in ROOT.rglob('*'):
            if path.is_symlink():
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertTrue(path.resolve().is_relative_to(ROOT.resolve()))


# Exercise the actual HTTP handler against atomic replacements, not just helpers.
import copy
import importlib.util
import tempfile
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer

SPEC = importlib.util.spec_from_file_location('demo_exporter', ROOT / 'exporter/exporter.py')
EXPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORTER)


class ExporterHTTP(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'scenarios.json'
        self.data = json.loads((ROOT / 'scenarios.json').read_text())
        self.save(self.data)
        self.server = HTTPServer(('127.0.0.1', 0), EXPORTER.Handler)
        self.server.source = self.path
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def save(self, value):
        next_file = self.path.with_suffix('.next')
        next_file.write_text(json.dumps(value))
        next_file.replace(self.path)

    def get(self):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{self.server.server_port}/metrics', timeout=3) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            with error:
                return error.code, error.read().decode()

    def test_full_population_explicit_mock_readings(self):
        code, body = self.get()
        self.assertEqual(200, code)
        rows = body.splitlines()
        for metric, count in [('demo_server_status',132), ('demo_component_status',132*21),
                              ('demo_switch_status',51), ('demo_mesh_status',648),
                              ('demo_interface_status',51*128), ('demo_port_status',51*32),
                              ('demo_transceiver_status',51*32)]:
            selected = [r for r in rows if r.startswith(metric+'{')]
            self.assertEqual(count,len(selected),metric)
            unknown = [r for r in selected if r.endswith(' 3')]
            self.assertEqual((84 if metric == 'demo_component_status' else 4) if metric in
                             ('demo_server_status','demo_component_status') else 0,len(unknown),metric)
            self.assertFalse(any(r.endswith(' 4') for r in selected),metric)
        self.assertIn('demo_mesh_status{fsp="FSPUnit3",vcc="VCCUnit1"} 2',body)
        self.assertIn('demo_port_status{port="1",source="VCCUnit1-switch"} 0',body)
        self.assertIn('demo_transceiver_status{port="1",source="VCCUnit1-switch"} 0',body)
        self.assertIn('cpu_temperature_celcius{fhs="FHS1",provenance="synthetic demo",source="CPU",unit="FSPUnit27"}',body)
        self.assertIn('node_hwmon_temp_celsius{',body)
        self.assertIn('nexus_ch_tempValue{',body)
        self.assertIn('demo_optic_temperature_celsius{',body)
        self.assertIn('demo_interface_rate_bytes_per_second{',body)
        self.assertNotIn('unit="FSPUnit1"} 40',body)
        self.assertEqual('STATIC DEMO: synthetic mock readings and synthetic peer inventory; not observed hardware',self.data['provenance'])

    def test_enum_hotread_both_link_ends_mesh_and_independent_hardware(self):
        for status, number in EXPORTER.STATES.items():
            self.data['servers']['fspu2-fhs1']['status'] = status
            self.data['servers']['fspu2-fhs1']['components']['psu1'] = status
            self.data['links'][2]['status'] = status
            self.data['physical_ports'] = {'vccu1-switch': {'1':'fault'}}
            self.data['transceivers'] = {'vccu1-switch': {'1':'ok'}}
            self.save(self.data)
            code,body = self.get()
            self.assertEqual(code,200)
            for prefix in ('demo_server_status{fhs="FHS1",provenance="static replay",unit="FSPUnit2"}',
                           'demo_component_status{component="psu1",fhs="FHS1",provenance="static replay",unit="FSPUnit2"}',
                           'demo_interface_status{interface="eth1/1/3",source="VCCUnit1-switch"}',
                           'demo_interface_status{interface="eth1/1/1",source="FSPUnit3-switch"}',
                           'demo_mesh_status{fsp="FSPUnit3",vcc="VCCUnit1"}'):
                self.assertIn(prefix+' '+str(number),body)
            self.assertIn('demo_port_status{port="1",source="VCCUnit1-switch"} 2',body)
            self.assertIn('demo_transceiver_status{port="1",source="VCCUnit1-switch"} 0',body)

    def test_interface_override_is_one_logical_link_and_hardware_independent(self):
        for status,number in EXPORTER.STATES.items():
            self.data['interfaces'] = {'fspu3-switch':{'eth1/1/1':status}}
            self.data['switches'] = {'vccu1-switch':status}
            self.save(self.data)
            code,body = self.get()
            self.assertEqual(200,code)
            for prefix in ('demo_interface_status{interface="eth1/1/3",source="VCCUnit1-switch"}',
                           'demo_interface_status{interface="eth1/1/1",source="FSPUnit3-switch"}',
                           'demo_mesh_status{fsp="FSPUnit3",vcc="VCCUnit1"}',
                           'demo_switch_status{source="VCCUnit1-switch"}'):
                self.assertIn(prefix+' '+str(number),body)
            self.assertIn('demo_port_status{port="1",source="VCCUnit1-switch"} 0',body)
            self.assertIn('demo_transceiver_status{port="1",source="VCCUnit1-switch"} 0',body)
        self.data['interfaces']['vccu1-switch']={'eth1/1/3':'fault'}
        self.save(self.data)
        self.assertEqual(503,self.get()[0])

    def test_invalid_and_recovery_no_stale_healthy(self):
        invalid = []
        for mutate in (
            lambda d: d.update(version=2),
            lambda d: d.update(typo=True),
            lambda d: d['servers']['fspu2-fhs1'].update(status='healthy'),
            lambda d: d['defaults'].update(status='healthy'),
            lambda d: d['servers']['fspu2-fhs1']['components'].update(typo='ok'),
            lambda d: d['links'][0]['ends'][0].update(interface='eth1/33/1'),
            lambda d: d['links'].append(d['links'][0]),
            lambda d: d.update(physical_ports={'vccu1-switch':{'0':'ok'}}),
            lambda d: d.update(readings=[{'server':'fspu2-fhs1','component':'cpu','metric':'cpu_temperature_celcius','value':float('nan'),'provenance':'synthetic demo'}]),
        ):
            data = copy.deepcopy(self.data)
            mutate(data)
            invalid.append(json.dumps(data))
        invalid.extend(['{', '{"version":1,"version":1}'])
        for raw in invalid:
            with self.subTest(raw=raw[:60]):
                self.path.write_text(raw)
                code,body = self.get()
                self.assertEqual(503,code)
                self.assertIn('invalid scenarios.json:',body)
                self.assertNotIn('demo_server_status{',body)
                self.save(self.data)
                self.assertEqual(200,self.get()[0])

    def test_optional_native_reading_only_when_explicit(self):
        self.data['defaults']['mock_readings'] = False
        self.data['readings'] = [{'server':'fspu2-fhs1','component':'cpu','metric':'cpu_temperature_celcius','value':42.5,'provenance':'synthetic demo'}]
        self.save(self.data)
        code,body = self.get()
        self.assertEqual(200,code)
        self.assertIn('cpu_temperature_celcius{fhs="FHS1",provenance="synthetic demo",source="CPU",unit="FSPUnit2"} 42.5',body)
        self.assertNotIn('fan1_rpm{',body)

    def test_bounded_mock_rate_roundtrip_and_schema(self):
        import re
        link = self.data['links'][2]
        link.update(rate_bps=2400000000, capacity_bps=10000000000)
        for status,expected in [('fault',0),('ok',300000000),('fault',0)]:
            link['status']=status
            self.save(self.data)
            code,body=self.get()
            self.assertEqual(200,code)
            self.assertNotIn('nexus_interfaces_octets{',body)
            for source,interface in [('VCCUnit1-switch','eth1/1/3'),('FSPUnit3-switch','eth1/1/1')]:
                rows=[line for line in body.splitlines() if line.startswith('demo_interface_rate_bytes_per_second{') and f'source="{source}"' in line and f'interface="{interface}"' in line]
                self.assertEqual(2,len(rows))
                self.assertTrue(all(float(line.rsplit(' ',1)[1])==expected for line in rows))
        for rate,capacity in [(11,10),(-1,10),(1,0),('1',10)]:
            link.update(rate_bps=rate,capacity_bps=capacity)
            self.save(self.data)
            self.assertEqual(503,self.get()[0])

    def test_mesh_capacity_preserved_across_status_and_endpoint_overrides(self):
        link = self.data['links'][2]
        link['capacity_bps'] = 60000000000
        prefix = 'demo_mesh_capacity_bps{fsp="FSPUnit3",vcc="VCCUnit1"}'
        for status,number in EXPORTER.STATES.items():
            self.data['interfaces'] = {'fspu3-switch':{'eth1/1/1':status}}
            self.save(self.data)
            code,body = self.get()
            self.assertEqual(200,code)
            rows = [r for r in body.splitlines() if r.startswith('demo_mesh_capacity_bps{')]
            self.assertEqual(648,len(rows))
            self.assertIn(prefix+' 60000000000',body)
            self.assertIn('demo_mesh_capacity_bps{fsp="FSPUnit1",vcc="VCCUnit1"} 100000000000',body)
            self.assertIn('demo_mesh_status{fsp="FSPUnit3",vcc="VCCUnit1"} '+str(number),body)
        self.data['defaults']['mock_readings'] = False
        self.save(self.data)
        code,body = self.get()
        self.assertEqual(200,code)
        self.assertNotIn('demo_mesh_capacity_bps{',body)
        self.assertIn('demo_mesh_status{',body)

    def test_adapter_queries_consume_status_contract(self):
        dashboards = {p.stem:json.loads(p.read_text()) for p in (ROOT/'grafana/dashboards').glob('*.json')}
        self.assertIn('demo_server_status{unit="$unit",fhs="$fhs"}', dashboards['fhs']['panels'][1]['targets'][0]['expr'])
        components = dashboards['fhs']['panels'][5:47:2]
        self.assertEqual(21,len(components))
        for panel,component in zip(components,EXPORTER.COMPONENTS):
            self.assertIn('component="'+component+'"', panel['targets'][0]['expr'])
            options = panel['fieldConfig']['defaults']['mappings'][0]['options']
            self.assertEqual({v['text'] for v in options.values()},set(EXPORTER.STATES))
        matrix = dashboards['mesh']['panels'][5]
        self.assertEqual(649,len(matrix['targets']))
        cells = [e for e in matrix['options']['root']['elements']
                 if e.get('config',{}).get('text',{}).get('mode') == 'field']
        expected = {f'VCCUnit{v} FSPUnit{f}' for v in range(1,25) for f in range(1,28)}
        self.assertEqual(648,len(cells))
        self.assertEqual(expected,{e['config']['text']['field'] for e in cells})
        capacity = matrix['targets'][:-1]
        self.assertEqual(expected,{t['legendFormat'] for t in capacity})
        self.assertEqual(648,len({t['refId'] for t in capacity}))
        for target in capacity:
            vcc, fsp = target['legendFormat'].split()
            self.assertEqual(
                f'((demo_mesh_capacity_bps{{vcc="{vcc}",fsp="{fsp}"}} / 1e9) '
                'and on(job,instance) (up{job="static-demo"} == 1)) or on() vector(-1)',
                target['expr'])
            self.assertTrue(target['instant'])
            self.assertFalse(target['range'])
        self.assertEqual({'text':'?', 'color':'#555963'},
                         matrix['fieldConfig']['defaults']['mappings'][0]['options']['-1'])
        self.assertEqual('background',matrix['targets'][-1]['refId'])
        self.assertIn('up{job="static-demo"} == 1',matrix['targets'][-1]['expr'])
        self.assertTrue(all(e['background']['color']['fixed'] == '#555963' for e in cells))
        self.assertEqual({name+' background' for name in expected},
                         {e['background']['color']['field'] for e in cells})
        for name in ('rack','mesh'):
            for panel in dashboards[name]['panels']:
                for element in panel.get('options',{}).get('root',{}).get('elements',[]):
                    self.assertNotIn(element.get('config',{}).get('text',{}).get('fixed'), ('ND','NoData','not deployed'))
        self.assertEqual(183,sum(len(p.get('targets',[])) for p in dashboards['rack']['panels']))

        self.assertEqual(161,len(dashboards['switch']['panels'][1]['targets']))
        self.assertIn('demo_transceiver_status',dashboards['switch']['panels'][3]['targets'][0]['expr'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
