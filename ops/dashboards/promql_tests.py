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
    # Exercise actual parent expression with a down lane, an up lane and absent inventory.
    from generate import build
    board=next(p for p in build()['switch']['panels'] if p['type']=='canvas')
    parent=next(t['expr'] for t in board['targets'] if t['legendFormat']=='Parent inventory state')
    for switch,state in [('VCCUnit1-switch',3),('FSPUnit1-switch',3),('FSPUnit4-switch',4)]:
        labels='{source="'+switch+'"}' if state==3 else '{}'
        cases.append(test(parent.replace('$switch',switch),[(labels,state)]))
    # Review note: execute actual generated freshness joins; missing logical hosts and failed shared target stay absent.
    for reading in [r for c in catalog if c['title']=='NVMe 0' for r in c['readings'] if r.get('label') in ('Composite','Controller live')]:
        expr='max('+reading_query(reading,None)+')'
        cases.append(test(expr,[('{}',36.85 if reading['name']=='node_hwmon_temp_celsius' else 1)]))
        cases.append(test(expr.replace('$fhs','FHS2'),[]))
        cases.append(test(expr.replace('$unit','FSPUnit1'),[]))
        cases.append(test(expr.replace('$node_job','node-down'),[]))
    from exact import mesh_rate, server_status, visual_status, inventory
    from visual_fixture import render
    # Parse the actual generated file feed, rather than an independent sample list.
    fixture_inputs=[series(line.rsplit(' ',1)[0].replace('{','{job="node-emulator",',1),0) for line in render().splitlines() if not line.startswith('#')]
    # Poison every actual identity, including the four missing FSP1 hosts.
    fixture_inputs += [series('fhs_visual_status{job="node-emulator",unit="'+h['unit']+'",fhs="'+h['fhs']+'",origin="visual_fixture"}',0)
                       for h in inventory() if h['kind']=='server' and h['deployed']]
    fixture_cases=[]
    for unit,expected in [('FSPUnit4',0),('VCCUnit5',0),('FSPUnit1',3),('FSPUnit2',1),('VCCUnit1',0)]:
        labels='{}' if expected!=3 else '{unit="FSPUnit1",fhs="FHS1"}'
        fixture_cases.append(test(server_status(health(unit,'FHS1'),unit,'FHS1'),[(labels,expected)]))
    for host in inventory():
        if host['kind']=='server' and host['deployed']:
            fixture_cases.append(test(visual_status(host['unit'],host['fhs']),[]))
    fixture_cases.append(test(server_status('vector(2)','FSPUnit4','FHS1'),[('{}',2)]))
    fixture_cases.append(test(visual_status('FSPUnit28','FHS1'),[]))
    fixture_cases.append(test(visual_status('VCCUnit5','FHS2'),[]))
    # Unsupported observations must stay absent even for a green fixture host.
    fixture_cases.append(test(reading_query({'name':'fan1_rpm'},None).replace('$unit','VCCUnit5'),[]))
    fixture_test={'interval':'1m','input_series':inputs+fixture_inputs,'promql_expr_test':fixture_cases}
    missing_expr=server_status(health('FSPUnit4','FHS1'),'FSPUnit4','FHS1')
    missing_expected=[('{unit="FSPUnit4",fhs="FHS1"}',3)]
    absent_test={'interval':'1m','input_series':[series('fhs_visual_status{job="node-emulator",unit="FSPUnit4",fhs="FHS1",origin="untrusted"}',0)],'promql_expr_test':[test(missing_expr,missing_expected)]}
    invalid_tests=[]
    for samples in ([], [series('fhs_visual_status{job="node-emulator",unit="FSPUnit4",fhs="FHS1",origin="visual_fixture"}',1)], [series('fhs_visual_status{job="other",unit="FSPUnit4",fhs="FHS1",origin="visual_fixture"}',0)]):
        invalid_tests.append({'interval':'1m','input_series':samples,'promql_expr_test':[test(missing_expr,missing_expected)]})
    stale_case=test(missing_expr,missing_expected);stale_case['eval_time']='3m'
    stale_test={'interval':'1m','input_series':[{'series':'fhs_visual_status{job="node-emulator",unit="FSPUnit4",fhs="FHS1",origin="visual_fixture"}','values':'0 _ _ _'}],'promql_expr_test':[stale_case]}
    rate_inputs=[]
    for iface,state in [('eth1/1/1','up'),('eth1/1/3','down')]:
        for direction in ('In','Out'):
            rate_inputs.append({'series':f'nexus_interfaces_octets{{job="switch",source="VCCUnit1-switch",interface="{iface}",dn="sys/intf/phys-[{iface}]/dbgIfHC{direction}"}}','values':'0+61016.94915254237x5'})
        rate_inputs.append({'series':f'nexus_lldp_id{{job="switch",source="VCCUnit1-switch",interface="{iface}",sysName="FSPUnit{1 if state=="up" else 3}-switch"}}','values':'1+0x5'})
        rate_inputs.append({'series':f'nexus_interfaces_vdcId{{job="switch",source="VCCUnit1-switch",interface="{iface}",operSt="{state}"}}','values':'1+0x5'})
    # Missing counters on an explicitly down, known link must not become zero.
    rate_inputs += [
        {'series':'nexus_lldp_id{job="switch",source="VCCUnit1-switch",interface="eth1/1/2",sysName="FSPUnit2-switch"}','values':'1+0x5'},
        {'series':'nexus_interfaces_vdcId{job="switch",source="VCCUnit1-switch",interface="eth1/1/2",operSt="down"}','values':'1+0x5'},
        # Peer counters are deliberately different; counting both ends is wrong.
        {'series':'nexus_interfaces_octets{job="switch",source="FSPUnit1-switch",interface="eth1/1/1",dn="sys/intf/phys-[eth1/1/1]/dbgIfHCIn"}','values':'0+60000000000x5'},
    ]
    rate_cases=[]
    for direction in ('In','Out'):
        for fsp in (1,3,2):
            expr=mesh_rate(direction).replace('$switch_job','switch').replace('$vccu','1').replace('$fspu',str(fsp))
            rate_cases.append({'expr':expr,'eval_time':'5m','exp_samples':[] if fsp==2 else [{'labels':'{}','value':1016.9491525423729*8/1e9}]})
    rate_test={'interval':'1m','input_series':rate_inputs,'promql_expr_test':rate_cases}
    print(json.dumps({'rule_files':[],'evaluation_interval':'1m','tests':[{'interval':'1m','input_series':inputs,'promql_expr_test':cases},rate_test,fixture_test,absent_test,stale_test]+invalid_tests},indent=2))

if __name__=='__main__':main()
