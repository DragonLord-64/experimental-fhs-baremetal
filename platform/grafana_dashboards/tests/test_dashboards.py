import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('generate',ROOT/'generate.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)

class Dashboards(unittest.TestCase):
    def test_current_configured_scope(self):
        dashboards=g.build()
        self.assertEqual(6,len(dashboards))
        rack=dashboards['rack']['panels']
        self.assertEqual(9,sum(p['type']=='canvas' for p in rack))
        elements=[e for p in rack if p['type']=='canvas' for e in p['options']['root']['elements']]
        self.assertEqual(9*42,sum(e['name'].startswith('U') for e in elements))
        self.assertEqual(44,sum('not deployed' in e['config']['text'].get('fixed','') for e in elements))
        self.assertEqual(116,sum('visual fixture / not observed' in e['config']['text'].get('fixed','') for e in elements))
        self.assertIn('SYNTHETIC',rack[0]['options']['content'])
        matrix=next(p for p in dashboards['mesh']['panels'] if p['type']=='canvas')
        cells=[e for e in matrix['options']['root']['elements'] if e['name'].startswith('VCCU') and ' FSPU' in e['name']]
        self.assertEqual(648,len(cells));self.assertEqual(636,sum(e['config']['text'].get('fixed')=='ND' for e in cells))
        self.assertEqual(12,len(matrix['targets']))

    def test_reproducible_full_inventory(self):
        dashboards=g.build()
        for k,d in dashboards.items():
            self.assertEqual(d,json.loads((ROOT/'generated'/f'{k}.json').read_text()))
        # Scaling query fixtures must not fabricate unreviewed physical placement.
        self.assertEqual(g.build()['rack']['panels'],g.build(24,27)['rack']['panels'])
        self.assertEqual(g.build()['rack']['panels'],g.build(1,3)['rack']['panels'])
        with self.assertRaises(ValueError):g.build(25,27)

    def test_physical_placement_validation(self):
        base=dict(id='a',rack='r',face='front',position_u=1,height_u=2)
        self.assertEqual({('r','front',1),('r','front',2)},g.validate_placement([base]))
        with self.assertRaisesRegex(ValueError,'Overlapping'):
            g.validate_placement([base,{**base,'id':'b','position_u':2}])
        # The opposite face is a separate elevation, not a front overlap.
        self.assertEqual(4,len(g.validate_placement([base,{**base,'id':'b','face':'rear'}])))
        for change in ({'position_u':42},{'position_u':0},{'height_u':0},{'face':'side'}):
            with self.assertRaises(ValueError):g.validate_placement([{**base,**change}])
        panels=g.build()['rack']['panels']
        boxes=[p for p in panels if p.get('targets')]
        self.assertTrue(any(e['placement']['height']==14 for p in panels if p['type']=='canvas' for e in p['options']['root']['elements']))
        # Native geometry may not overlap, including empty U and slot labels.
        occupied=set()
        for p in panels:
            pos=p['gridPos']
            for x in range(pos['x'],pos['x']+pos['w']):
                for y in range(pos['y'],pos['y']+pos['h']):
                    self.assertNotIn((x,y),occupied,p['title'])
                    occupied.add((x,y))

    def test_default_cli_matches_checked_in_candidate(self):
        with tempfile.TemporaryDirectory() as output:
            subprocess.run([sys.executable,str(ROOT/'generate.py'),'--output',output],check=True)
            for key in g.DEST:
                self.assertEqual((ROOT/'generated'/f'{key}.json').read_bytes(),(Path(output)/f'{key}.json').read_bytes())

    def test_navigation_encoding_and_destinations(self):
        link=g.url('interface',switch='rack A/switch & 1',interface='eth1/1/3')
        parsed=parse_qs(urlsplit(link).query)
        self.assertEqual(['rack A/switch & 1'],parsed['var-switch'])
        self.assertEqual(['eth1/1/3'],parsed['var-interface'])
        self.assertIn('${target_interface:percentencode}',link)
        self.assertIn('${__url_time_range}',link)
        for k in g.DEST:self.assertIn('var-target_'+k+'=',link)
        self.assertIn('var-ds=${ds:percentencode}',link)
        self.assertNotIn('localhost',link)
        dynamic=g.url('interface',dynamic={'interface':'${__data.fields.interface:percentencode}'})
        self.assertEqual(1,dynamic.count('var-interface='))
        self.assertIn('var-interface=${__data.fields.interface:percentencode}',dynamic)
        for d in g.build(1,3).values():
            variables={v['name']:v for v in d['templating']['list']}
            for k,(_,uid) in g.DEST.items():
                v=variables['target_'+k]
                self.assertEqual(0,v['hide']);self.assertEqual(uid,v['current']['value'])
                self.assertNotEqual(uid,v['current']['text'])
            self.assertTrue(all(l['url'].startswith('/d/${target_') for l in d['links']))

    def test_missing_data_and_psu_semantics(self):
        expr=g.health('FSPUnit2','FHS1')
        self.assertIn('unit="FSPUnit2",fhs="FHS1"',expr)
        self.assertNotIn('vector(0)',expr)
        self.assertNotIn('up * 0',expr)
        rack=g.build(1,3)['rack']['panels']
        for p in rack:
            if p['title']=='Unit hardware health':
                mapping=p['fieldConfig']['defaults']['mappings'][0]['options']
                self.assertEqual('Degraded',mapping['1']['text'])
                self.assertEqual('Unknown / No data',p['fieldConfig']['defaults']['noValue'])
        missing=[t for p in rack for t in p.get('targets',[]) if 'FSPUnit1-FHS' in t.get('legendFormat','')]
        self.assertEqual(4,len(missing))
        self.assertTrue(all('sts_psu' in t['expr'] for t in missing))

    def test_mesh_has_both_ends_and_no_host_dependency(self):
        expr=g.mesh_query()
        self.assertIn('min by(vcc,fsp)',expr)
        self.assertIn('source=~"VCCUnit.*"',expr)
        self.assertIn('source=~"FSPUnit.*"',expr)
        self.assertIn('group_left(sysName)',expr)
        self.assertNotIn('sts_psu',expr)
        self.assertNotIn('node_',expr)
        self.assertNotIn('vector(0)',expr)

    def test_opposite_endpoint_navigation(self):
        detail=g.build(1,3)['interface']
        peer=next(p for p in detail['panels'] if p['title']=='Last-known peer')
        self.assertIn('"peer_role","$1","sysName","(VCC|FSP)Unit([0-9]+)-switch"',peer['targets'][0]['expr'])
        link=peer['fieldConfig']['defaults']['links'][0]['url']
        unit='${__data.fields.peer_role:percentencode}Unit${__data.fields.peer_number:percentencode}'
        for variable,value in [('unit',unit),('switch',unit+'-switch'),('interface','${__data.fields.portIdV:percentencode}')]:
            self.assertIn('var-'+variable+'='+value,link)
            self.assertEqual(1,link.count('var-'+variable+'='))

    def test_numeric_readings_and_peer_identity_are_visible(self):
        dashboards=g.build()
        readings=[p for p in dashboards['fhs']['panels'] if p['title'].endswith('· readings')]
        self.assertGreater(len(readings),20)
        self.assertTrue(all(p['type']=='stat' and p['options']['textMode']=='value_and_name' and p['gridPos']['h']==3 for p in readings))
        self.assertTrue(all(p['gridPos']['x'] in (2,14) for p in readings))
        status=[p for p in dashboards['fhs']['panels'] if p['type']=='stat' and p['title']=='']
        self.assertEqual(21,len(status));self.assertTrue(all(p['options']['textMode']=='value' for p in status))
        peer=next(p for p in dashboards['interface']['panels'] if p['title']=='Last-known peer')
        options=peer['transformations'][0]['options']
        self.assertEqual({'sysName':0,'portIdV':1,'interface':2,'mgmtIp':3},options['indexByName'])
        for field in ('Time','__name__','capability','dn'):
            self.assertTrue(options['excludeByName'][field])
        self.assertTrue(any(p['title']=='LLDP diagnostics' for p in dashboards['interface']['panels']))

    def test_source_duplicate_consolidation(self):
        p=json.loads((ROOT/'PROVENANCE.json').read_text())
        self.assertEqual(2,len(p['official_unique_sources']))
        duplicate=next(x for x in p['official_unique_sources'] if len(x['paths'])==2)
        self.assertEqual('45049a1ac999fea347e84c50d826b27d8f1e943c9d15ffa0d3031ce6533f921d',duplicate['sha256'])

if __name__=='__main__':unittest.main()

class PrototypeContracts(unittest.TestCase):
    def test_explicit_inventory_and_layout(self):
        spec=importlib.util.spec_from_file_location('adapter',ROOT/'exact.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
        items=a.inventory();self.assertEqual(183,len(items));self.assertEqual(23,sum(p['deployed'] for p in items))
        self.assertEqual(132,sum(p['kind']=='server' for p in items));g.validate_placement(items)
        for rack in range(1,10):
            units={p['unit'] for p in items if p['rack']==rack}
            self.assertEqual(4 if rack<=6 else 0,sum(u.startswith('VCC') for u in units));self.assertEqual(3,sum(u.startswith('FSP') for u in units))
    def test_no_mock_telemetry_or_config_and_switch_geometry(self):
        d=g.build();sw=next(p for p in d['switch']['panels'] if p['type']=='canvas')
        self.assertEqual(128,sum(e['name'].endswith(' link') and ' L' in e['name'] for e in sw['options']['root']['elements']))
        self.assertEqual(128,len([t for t in sw['targets'] if t['legendFormat'].endswith(' state') and t['legendFormat'] != 'Parent inventory state']))
        self.assertEqual(1,len([t for t in sw['targets'] if t['legendFormat'] == 'Parent inventory state']))
        all_queries=[t['expr'] for v in d.values() for p in v['panels'] for t in p.get('targets',[])]
        for query in all_queries:
            self.assertNotIn('cisco_lane_snapshot',query);self.assertNotIn('server_component_',query);self.assertNotIn('vlan_catalog_info',query)
        for p in d['vlan']['panels']:
            for t in p.get('targets',[]):
                self.assertNotIn('vlan_match_',t['expr']);self.assertNotIn('vlan_catalog_',t['expr'])
        self.assertTrue(any('Chassis temperature'==p['title'] for p in d['switch']['panels']))
        self.assertTrue(any('Transceiver' in p['title'] for p in d['switch']['panels']))

class DrilldownClassification(unittest.TestCase):
    def test_status_panels_have_distinct_absent_and_missing_states(self):
        d=g.build()
        status=[next(p for p in d['fhs']['panels'] if p['title']=='Overall hardware health'),next(p for p in d['interface']['panels'] if p['title']=='Interface operational state'),next(p for p in d['mesh']['panels'] if 'observed status' in p['title'])]
        for p in status:
            values=next(m['options'] for m in p['fieldConfig']['defaults']['mappings'] if m['type']=='value')
            self.assertEqual('unknown',values['3']['text']);self.assertEqual('not deployed',values['4']['text'])
            self.assertIn('or on() vector(4)',p['targets'][0]['expr'])
            self.assertIn('3 * (',p['targets'][0]['expr'])
    def test_display_fallback_is_never_used_for_numeric_readings(self):
        for p in g.build()['fhs']['panels']:
            if p['title'].endswith('· readings'):
                for t in p['targets']:self.assertNotIn('or on() vector(4)',t['expr'])
