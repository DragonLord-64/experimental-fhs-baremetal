#!/usr/bin/env python3
"""Generate additive lab Helm overlays from current deployed release values."""
import json
import os
from pathlib import Path
import subprocess
import sys
from topology import configured

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT/'.runtime'
HELM = os.environ.get('HELM_BIN', str(Path.home()/'.local/bin/helm'))
H = [HELM,'--kube-context','fhs-test','--namespace','fhs-platform']

def scrape_configs(t):
    entries=[]
    for host in t['hosts']:
        port=9111 if host['telemetry']=='psu1_fault' else 9110
        endpoint=f'fhs-emulator.fhs-emulators.svc.cluster.local:{port}'
        if host['telemetry']=='missing':
            endpoint='missing-telemetry.fhs-emulators.svc.cluster.local:9110'
        entries.append({'targets':[endpoint], 'labels':{k:host[k] for k in ('unit','role','fhs')} | {'fhs_name':host['name'],'synthetic':'true','emulation_mode':'shared'}})
    return [
        {'job_name':'fhs-emulator','scrape_interval':'15s','scrape_timeout':'5s','static_configs':entries,
         'metric_relabel_configs':[{'source_labels':['__name__'],'regex':'(?:.*temperature.*|.*_fan_rpm|.*power_watts|sts_.*|test_.*|num_metrics_.*|.*voltage_volts)','action':'keep'}]},
        {'job_name':'node-emulator','scrape_interval':'15s','static_configs':[{'targets':['fhs-emulator.fhs-emulators.svc.cluster.local:9100'],'labels':{'synthetic':'true','emulation_mode':'shared'}}]},
    ]

def overlays(prom,telegraf,t,remove=False):
    prom_files=prom.get('serverFiles',{}).copy()
    config=prom_files.get('prometheus.yml',{}).copy()
    config['scrape_configs']=[j for j in config.get('scrape_configs',[]) if j.get('job_name') not in ('fhs-emulator','node-emulator')]+([] if remove else scrape_configs(t))
    prom_files['prometheus.yml']=config
    tc=telegraf['config'].copy()
    inputs=json.loads(json.dumps(tc['inputs']))
    for item in inputs:
        if 'cisco_telemetry_mdt' in item:
            if remove:
                item['cisco_telemetry_mdt'].get('aliases',{}).pop('nexus_lldp',None)
                item['cisco_telemetry_mdt'].get('dmes',{}).pop('dnpath_lldp',None)
                continue
            item['cisco_telemetry_mdt'].setdefault('aliases',{})['nexus_lldp']='sys/lldp'
            item['cisco_telemetry_mdt'].setdefault('dmes',{})['dnpath_lldp']=json.dumps({'Name':'sys/lldp','prop':[{'Key':k,'Value':'string'} for k in ('sysDesc','portDesc','portIdV','chassisIdV','sysName','name')]+[{'Key':'id','Value':'integer'}]})
    tc['inputs']=inputs
    processors=json.loads(json.dumps(tc.get('processors',[])))
    processors=[p for p in processors if not p.get('regex',{}).get('namepass')==['nexus_interfaces','nexus_lldp']]
    if not remove:
        processors.append({'regex':{'namepass':['nexus_interfaces','nexus_lldp'],'tags':[{'key':'dn','pattern':r'^.*(?:phys|if)-\[(?P<interface>[^\]]+)\].*$','replacement':'${interface}','result_key':'interface'}]}})
    tc['processors']=processors
    for output in tc['outputs']:
        if 'prometheus_client' in output:
            output['prometheus_client']['string_as_label']=True
    return {'serverFiles':prom_files},{'config':tc}

def main():
    RUNTIME.mkdir(exist_ok=True,mode=0o700)
    values=[]
    for release in ('prometheus','telegraf'):
        data=json.loads(subprocess.check_output(H+['get','values',release,'-o','json'],text=True))
        baseline=RUNTIME/(release+'-before.json')
        if '--remove' in sys.argv and not baseline.exists():
            raise SystemExit('No recorded pre-emulator values; refusing to remove integration from an unowned release.')
        if not baseline.exists():
            baseline.write_text(json.dumps(data,indent=2)+'\n');baseline.chmod(0o600)
        values.append(data)
    for release,data in zip(('prometheus','telegraf'),overlays(*values,configured(),remove='--remove' in sys.argv)):
        if '--remove' in sys.argv and release=='telegraf':
            before=json.loads((RUNTIME/'telegraf-before.json').read_text())
            original=next(i['cisco_telemetry_mdt'] for i in before['config']['inputs'] if 'cisco_telemetry_mdt' in i)
            current=next(i['cisco_telemetry_mdt'] for i in data['config']['inputs'] if 'cisco_telemetry_mdt' in i)
            for section,key in [('aliases','nexus_lldp'),('dmes','dnpath_lldp')]:
                if key in original.get(section,{}):
                    current.setdefault(section,{})[key]=original[section][key]
        target=RUNTIME/(release+'-overlay.json')
        target.write_text(json.dumps(data,indent=2)+'\n');target.chmod(0o600)
    print('Prepared additive overlays; existing platform jobs, inputs and outputs retained.')

if __name__=='__main__':
    main()
