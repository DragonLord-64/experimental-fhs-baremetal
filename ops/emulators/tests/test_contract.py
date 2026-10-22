import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fixture import node_metrics
from topology import topology,configured
from render import render
from integration import overlays,scrape_configs

class Contracts(unittest.TestCase):
 def test_full_topology_and_scenarios(self):
  t=topology()
  self.assertEqual((len(t['hosts']),len(t['switches']),len(t['mesh_links'])),(132,51,648))
  self.assertEqual(sum(h['telemetry']=='missing' for h in t['hosts']),4)
  self.assertTrue(all(h['unit']=='FSPUnit1' for h in t['hosts'] if h['telemetry']=='missing'))
  failed=[h for h in t['hosts'] if h['telemetry']=='psu1_fault']
  self.assertEqual([(h['unit'],h['fhs']) for h in failed],[('FSPUnit2','FHS1')])
  bad=[e for e in t['mesh_links'] if e['state']=='down']
  self.assertEqual(bad,[{'a_switch':'VCCUnit1-switch','a_port':'eth1/1/3','b_switch':'FSPUnit3-switch','b_port':'eth1/1/1','state':'down'}])
  for e in t['mesh_links']:
   for source,local,remote,peer in [(e['a_switch'],e['a_port'],e['b_switch'],e['b_port']),(e['b_switch'],e['b_port'],e['a_switch'],e['a_port'])]:
    sw=next(s for s in t['switches'] if s['name']==source)
    link=next(l for l in sw['links'] if l['local_port']==local)
    self.assertEqual((link['neighbor']['name'],link['remote_port'],link['state']),(remote,peer,e['state']))
  macs=[i['node_mac'] for h in t['hosts'] for i in h['interfaces']]
  self.assertEqual(len(macs),len(set(macs)))

 def test_no_data_and_node_labels(self):
  t=topology(1,3);data=node_metrics(t)
  for h in t['hosts']:
   if h['telemetry']=='missing':
    self.assertNotIn('fhs_name="'+h['name']+'"',data)
   else:
    for link in h['interfaces']:
     self.assertIn('address="'+link['node_mac']+'"',data)
     self.assertIn('ifalias="'+link['switch']+':'+link['switch_port']+'"',data)
  configs=scrape_configs(t)
  self.assertEqual(len(configs[0]['static_configs']),13)
  self.assertEqual(sum('missing-telemetry' in e['targets'][0] for e in configs[0]['static_configs']),4)
  self.assertEqual(sum(':9111' in e['targets'][0] for e in configs[0]['static_configs']),1)
  self.assertFalse(any(line.startswith(('up ', 'up{')) for line in data.splitlines()))

 def test_additive_integration(self):
  p={'serverFiles':{'prometheus.yml':{'scrape_configs':[{'job_name':'existing'}],'rule_files':['existing.yml']}}}
  t={'config':{'inputs':[{'internal':{}},{'cisco_telemetry_mdt':{'aliases':{'existing':'sys/ch'}}}],'outputs':[{'prometheus_client':{'metric_version':2}}]}}
  po,to=overlays(p,t,topology(1,3))
  self.assertEqual(po['serverFiles']['prometheus.yml']['scrape_configs'][0]['job_name'],'existing')
  self.assertEqual(po['serverFiles']['prometheus.yml']['rule_files'],['existing.yml'])
  self.assertIn({'internal':{}},to['config']['inputs'])
  self.assertEqual(to['config']['inputs'][1]['cisco_telemetry_mdt']['aliases']['existing'],'sys/ch')
  po2,to2=overlays(po,to,topology(1,3))
  self.assertEqual(po,po2);self.assertEqual(to,to2)

 def test_exporters_and_isolation(self):
  docs=render()['items']
  for d in docs:
   if d['kind']=='Namespace':continue
   self.assertEqual(d['metadata']['namespace'],'fhs-emulators')
   if d['kind']=='Service':self.assertEqual(d['spec']['type'],'ClusterIP')
   if d['kind']!='Deployment':continue
   spec=d['spec']['template']['spec']
   self.assertFalse(spec['automountServiceAccountToken'])
   self.assertNotIn('hostPath',str(spec));self.assertNotIn('hostNetwork',spec)
   for c in spec['containers']:
    self.assertFalse(c['securityContext']['allowPrivilegeEscalation'])
    self.assertTrue(c['securityContext']['readOnlyRootFilesystem'])
  fhs,fault,node=docs[2]['spec']['template']['spec']['containers']
  self.assertIn('--emulation_mode',fhs['args'])
  self.assertIn('--ipmi_emulation_metrics_filepath',fault['args'])
  self.assertIn('--collector.disable-defaults',node['args'])
  self.assertIn('--collector.textfile',node['args'])
  cm=docs[1]['data'];self.assertLess(sum(len(v.encode()) for v in cm.values()),1024*1024)
  self.assertNotIn('value: [',cm['fhstelemetry-fpga.yaml'])
  self.assertIn('name: "STS_PSU1_FAN"\n    value: 1.0',cm['fhstelemetry-ipmi-psu1-fault.yaml'])
  self.assertIn('name: "STS_PSU1_FAN"\n    value: 0.0',cm['fhstelemetry-ipmi.yaml'])

if __name__=='__main__':unittest.main()
