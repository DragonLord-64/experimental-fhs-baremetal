import json
import re
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from importlib import import_module
check_configmap=import_module("apply").check_configmap
from fixture import node_metrics
from topology import topology,configured
from render import render
from integration import overlays,scrape_configs,restore_outputs,restore_mdt

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

 # Review note: native chassis fan/CPU flags are dashboard inputs; retain them without widening unrelated names.
 def test_native_component_health_metrics_survive_relabel(self):
  config=scrape_configs(topology(4,3))[0]
  keep=config['metric_relabel_configs'][0]
  self.assertEqual((keep['source_labels'],keep['action']),(['__name__'],'keep'))
  for name in ('fan1_rpm','fan2_rpm','prochot_cpu','cpu1_thermtrip','sts_cpu_mce','volt_12v_volts','volt_3v_volts','watchdog2','chassis_intr'):
   self.assertIsNotNone(re.fullmatch(keep['regex'],name),name)
  for name in ('fan3_rpm','prochot_cpu_extra','cpu2_thermtrip','volt_5v_volts','watchdog2_extra','unrelated_metric'):
   self.assertIsNone(re.fullmatch(keep['regex'],name),name)
  self.assertEqual(sum('missing-telemetry' in e['targets'][0] for e in config['static_configs']),4)
  self.assertEqual(sum(':9111' in e['targets'][0] for e in config['static_configs']),1)

 # Review note: missing hosts must not gain NVMe state; present hosts get reference-shaped synthetic telemetry.
 def test_synthetic_nvme_component_metrics(self):
  t=topology(4,3);data=node_metrics(t)
  self.assertIn('# TYPE node_hwmon_temp_celsius gauge',data)
  self.assertIn('# TYPE node_nvme_info gauge',data)
  temperatures=[line for line in data.splitlines() if line.startswith('node_hwmon_temp_celsius{')]
  info=[line for line in data.splitlines() if line.startswith('node_nvme_info{')]
  self.assertEqual((len(temperatures),len(info)),(24,24))
  for host in t['hosts']:
   rows=[line for line in temperatures+info if 'fhs_name="'+host['name']+'"' in line]
   self.assertEqual(len(rows),0 if host['telemetry']=='missing' else 4)
   for line in rows:
    if line.startswith('node_hwmon'):
     self.assertRegex(line,r'chip="nvme_nvme[01]".*sensor="temp1".*} 36\.85$')
    else:
     self.assertIn('state="live"',line)
     self.assertIn('serial="synthetic-',line)

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
  fhs,fault,node,*caches=docs[2]['spec']['template']['spec']['containers']
  self.assertEqual(len(caches),2)
  self.assertTrue(all(c['readinessProbe']['httpGet']['path']=='/ready' for c in caches))
  self.assertIn('--emulation_mode',fhs['args'])
  self.assertIn('--ipmi_emulation_metrics_filepath',fault['args'])
  self.assertIn('--collector.disable-defaults',node['args'])
  self.assertIn('--collector.textfile',node['args'])
  cm=docs[1]['data'];self.assertLess(sum(len(v.encode()) for v in cm.values()),1024*1024)
  self.assertNotIn('value: [',cm['fhstelemetry-fpga.yaml'])
  self.assertIn('name: "STS_PSU1_FAN"\n    value: 1.0',cm['fhstelemetry-ipmi-psu1-fault.yaml'])
  self.assertIn('name: "STS_PSU1_FAN"\n    value: 0.0',cm['fhstelemetry-ipmi.yaml'])

 def test_overlay_does_not_mutate_observed_release_values(self):
  # Saved release values are evidence for cleanup and review of platform changes.
  prom={'serverFiles':{'prometheus.yml':{'scrape_configs':[{'job_name':'existing'}]}}}
  telegraf={'config':{'inputs':[{'cisco_telemetry_mdt':{}}],
                      'outputs':[{'prometheus_client':{'string_as_label':False}}]}}
  before=json.loads(json.dumps([prom,telegraf]))
  overlays(prom,telegraf,topology(1,3))
  self.assertEqual([prom,telegraf],before)

 def test_changed_fixtures_roll_workers_that_read_only_at_startup(self):
  with patch('render.configured', return_value=topology(1,3)):
   small=render()
   self.assertEqual(small,render())
  with patch('render.configured', return_value=topology()):
   full=render()
  def checksums(doc):
   return [d['spec']['template']['metadata']['annotations']['checksum/fixtures']
           for d in doc['items'] if d['kind']=='Deployment']
  self.assertEqual(len(set(checksums(small))),1)
  self.assertNotEqual(checksums(small),checksums(full))

 def test_fixture_migration_refuses_external_edits(self):
  desired={'data':{'topology.json':'new'}}
  current={'metadata':{'labels':{'app.kubernetes.io/part-of':'fhs-emulators'},
                      'annotations':{'kubectl.kubernetes.io/last-applied-configuration':json.dumps({'data':{'topology.json':'old'}})}},
           'data':{'topology.json':'old'}}
  check_configmap(current,desired)
  current['data']['topology.json']='operator-edit'
  with self.assertRaisesRegex(RuntimeError,'changed outside'):
   check_configmap(current,desired)
  current['metadata']['labels']={}
  with self.assertRaisesRegex(RuntimeError,'ownership'):
   check_configmap(current,desired)
  with self.assertRaisesRegex(RuntimeError,'ownership'):
   check_configmap(current,desired,managed=True)

 def test_cleanup_restores_mdt_section_presence(self):
  for original in ({}, {'dmes':{}}, {'dmes':{'dnpath_lldp':'original'}}):
   current={'dmes':{}}
   restore_mdt(current,original)
   self.assertEqual(current,original)
  current={'dmes':{'operator':'preserved'}}
  restore_mdt(current,{})
  self.assertEqual(current,{'dmes':{'operator':'preserved'}})

 def test_cleanup_restores_output_settings(self):
  for original in ({}, {'string_as_label':False}, {'string_as_label':True}):
   baseline={'outputs':[{'prometheus_client':dict(original)}]}
   current={'outputs':[{'prometheus_client':{'string_as_label':True,'metric_version':2}}]}
   restore_outputs(current,baseline)
   self.assertEqual(current['outputs'][0]['prometheus_client'],dict(original,metric_version=2))
  with self.assertRaises(ValueError):
   restore_outputs({'outputs':[]},baseline)

if __name__=='__main__':unittest.main()
