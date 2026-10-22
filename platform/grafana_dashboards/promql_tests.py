#!/usr/bin/env python3
"""Write Promtool fixtures that execute the actual generated expressions."""
import json
from generate import health, mesh_query, reading_query, ROOT

def series(name,value):return {'series':name,'values':f'{value} {value}'}

def main():
    inputs=[]
    catalog=json.loads((ROOT/'components.json').read_text())
    readings={r['name']:r for c in catalog for r in c['readings'] if not r.get('node_job')}
    for unit in ('FSPUnit2','VCCUnit1','FSPUnit4'):
        count=1 if unit.startswith('VCC') else (3 if unit=='FSPUnit4' else 4)
        for h in range(1,count+1):
            for name,r in readings.items():
                value=40 if r.get('kind')=='temperature' else (8000 if r.get('kind')=='fan' else 0)
                if unit=='FSPUnit2' and h==1 and name=='sts_psu1_fan':value=1
                inputs.append(series(f'{name}{{job="fhs",unit="{unit}",fhs="FHS{h}"}}',value))
    for a,ap,b,bp,state in [('VCCUnit1-switch','eth1/1/3','FSPUnit3-switch','eth1/1/1','down'),('VCCUnit1-switch','eth1/1/1','FSPUnit1-switch','eth1/1/1','up')]:
        for src,port,peer,remote in [(a,ap,b,bp),(b,bp,a,ap)]:
            inputs.append(series(f'nexus_interfaces_vdcId{{job="switch",source="{src}",interface="{port}",operSt="{state}"}}',1))
            inputs.append(series(f'nexus_lldp_id{{job="switch",source="{src}",interface="{port}",sysName="{peer}",portIdV="{remote}"}}',1))
    # Review note: node metrics carry logical identity while their shared scrape target up does not.
    inputs.append(series('up{job="node",instance="shared"}',1))
    inputs.append(series('node_hwmon_temp_celsius{job="node",instance="shared",unit="FSPUnit2",fhs="FHS1",chip="nvme_nvme0",sensor="temp1"}',36.85))
    inputs.append(series('node_nvme_info{job="node",instance="shared",unit="FSPUnit2",fhs="FHS1",device="nvme0",state="live"}',1))
    inputs.append(series('up{job="node-down",instance="shared"}',0))
    inputs.append(series('node_nvme_info{job="node-down",instance="shared",unit="FSPUnit2",fhs="FHS1",device="nvme0",state="live"}',1))
    def test(expr,expected):
        return {'expr':expr.replace('$node_job','node').replace('$node_instance','.*').replace('$unit','FSPUnit2').replace('$fhs','FHS1').replace('$instance','.*').replace('$job','fhs').replace('$switch_job','switch'),'eval_time':'1m','exp_samples':[{'labels':labels,'value':value} for labels,value in expected]}
    cases=[test(health('FSPUnit2'),[('{}',1)]),test(health('FSPUnit2','FHS2'),[('{}',0)]),test(health('VCCUnit1'),[('{}',0)])]
    cases.append(test(health('FSPUnit4'),[]))
    cases += [test(health('FSPUnit1',f'FHS{h}'),[]) for h in range(1,5)]
    cases.append(test(mesh_query(),[('{vcc="VCCUnit1",fsp="FSPUnit1"}',1),('{vcc="VCCUnit1",fsp="FSPUnit3"}',0)]))
    # Review note: execute actual generated freshness joins; missing logical hosts and failed shared target stay absent.
    for reading in [r for c in catalog if c['title']=='NVMe 0' for r in c['readings'] if r.get('label') in ('Composite','Controller live')]:
        expr='max('+reading_query(reading,None)+')'
        cases.append(test(expr,[('{}',36.85 if reading['name']=='node_hwmon_temp_celsius' else 1)]))
        cases.append(test(expr.replace('$fhs','FHS2'),[]))
        cases.append(test(expr.replace('$unit','FSPUnit1'),[]))
        cases.append(test(expr.replace('$node_job','node-down'),[]))
    print(json.dumps({'rule_files':[],'evaluation_interval':'1m','tests':[{'interval':'1m','input_series':inputs,'promql_expr_test':cases}]},indent=2))

if __name__=='__main__':main()
