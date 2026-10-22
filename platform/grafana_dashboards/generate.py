#!/usr/bin/env python3
"""Native dashboard generator. Topology is explicit configured metadata, not discovery."""
import argparse
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
DS = {'type': 'prometheus', 'uid': '${ds}'}
DEST = {'rack': ('Infrastructure rack', 'fhs-infra-rack'), 'mesh': ('VCC to FSP mesh', 'fhs-infra-mesh'), 'fhs': ('FHS telemetry', 'fhs-infra-server'), 'switch': ('Switch overview', 'fhs-infra-switch'), 'interface': ('Switch interface', 'fhs-infra-interface'), 'vlan': ('VLAN configuration', 'fhs-infra-vlan')}


def url(view, dynamic=None, **selected):
    values = {k: '${'+k+':percentencode}' for k in ('ds', 'job', 'node_job', 'switch_job', 'unit', 'fhs', 'instance', 'node_instance', 'switch', 'interface', 'vccu', 'fspu', 'port', 'vlan')}
    values.update({f'target_{k}': '${target_'+k+':percentencode}' for k in DEST})
    values.update({k: quote(str(v), safe='') for k, v in selected.items()})
    values.update(dynamic or {})
    return '/d/${target_'+view+':percentencode}?' + '&'.join('var-'+k+'='+v for k,v in values.items()) + '&${__url_time_range}'


def variable(name, label, query, default=None):
    return {'name':name, 'label':label, 'type':'query', 'datasource':DS, 'query':{'query':query,'refId':name}, 'definition':query, 'refresh':1, 'sort':1, 'multi':False, 'includeAll':False, **({'current':{'text':default,'value':default}} if default else {})}


def variables():
    result = [{'name':'ds','label':'Datasource','type':'datasource','query':'prometheus','current':{'text':'Prometheus','value':'prometheus'}}]
    result += [{'name':'target_'+key,'label':name+' dashboard','type':'custom','query':name+' : '+uid,'current':{'text':name,'value':uid},'hide':0} for key,(name,uid) in DEST.items()]
    for name,label,query,default in [
        ('job','FHS job','label_values(sts_psu1_fan, job)',None),
        ('node_job','Node job','label_values(node_network_info, job)',None),
        ('switch_job','Switch job','label_values(nexus_interfaces_vdcId, job)',None),
        ('unit','Unit','label_values(up{fhs_name!=""}, unit)','FSPUnit2'),
        ('fhs','FHS member','label_values(up{unit="$unit",fhs_name!=""}, fhs)','FHS1'),
        ('instance','FHS instance','label_values(up{job="$job",unit="$unit",fhs="$fhs"}, instance)',None),
        ('node_instance','Node instance','label_values(up{job="$node_job",unit="$unit",fhs="$fhs"}, instance)',None),
        ('switch','Switch','label_values(nexus_interfaces_vdcId{job="$switch_job"}, source)','FSPUnit2-switch'),
        ('interface','Interface','label_values(nexus_interfaces_vdcId{job="$switch_job",source="$switch"}, interface)','eth1/1/1')]:
        result.append(variable(name,label,query,default))
    for v in result:
        if v['name'] in ('instance','node_instance'):
            v.update({'includeAll':True,'allValue':'.*','current':{'text':'All','value':'$__all'}})
    return result


def health(unit, fhs=None):
    # Only observed hardware values determine status; no or vector(0).
    match = 'job="$job",unit="'+unit+'"' + (',fhs="'+fhs+'"' if fhs else '')
    maximum = 'max(sts_psu1_fan{'+match+'} or sts_psu2_fan{'+match+'})'
    expected = 1 if fhs or unit.startswith('VCC') else 4
    native={r['name'] for c in json.loads((ROOT/'components.json').read_text()) for r in c['readings'] if not r.get('node_job')}
    # All native readings must cover every member before claiming Healthy.
    complete=' and on() '.join('(count(count by(fhs) ('+name+'{'+match+'})) == '+str(expected)+')' for name in sorted(native))
    temperatures=sorted({r['name'] for c in json.loads((ROOT/'components.json').read_text()) for r in c['readings'] if r.get('kind')=='temperature' and not r.get('node_job')})
    hot='max({__name__=~"'+'|'.join(temperatures)+'",'+match+'})'
    fan='min({__name__=~"fan1_rpm|fan2_rpm",'+match+'})'
    failed='('+hot+' >= 85) or on() ('+fan+' < 1000)'
    degraded='('+maximum+' > 0) or on() ('+hot+' >= 70) or on() ('+fan+' < 4000)'
    return '(vector(2) and on() ('+failed+')) or on() (vector(1) and on() ('+degraded+')) or on() (('+maximum+' * 0) and on() ('+complete+'))'



def panel(title, expr, x=0,y=0,w=6,h=4, kind='stat', link=None, states=None):
    result = {'title':title,'type':kind,'gridPos':{'x':x,'y':y,'w':w,'h':h},'datasource':DS,
              'targets':[{'refId':'A','expr':expr,'instant':kind!='timeseries','range':kind=='timeseries','format':'table' if kind=='table' else 'time_series'}],
              'fieldConfig':{'defaults':{'noValue':'Unknown / No data','color':{'mode':'thresholds'},'thresholds':{'mode':'absolute','steps':[{'color':'green','value':None},{'color':'red','value':1}]},'mappings':[]},'overrides':[]},
              'options':{'reduceOptions':{'calcs':['lastNotNull'],'values':False},'colorMode':'background','textMode':'auto','graphMode':'none'}}
    if states:
        result['fieldConfig']['defaults']['mappings']=[{'type':'value','options':{str(k):{'text':v[0],'color':v[1]} for k,v in states.items()}}]
    result['fieldConfig']['defaults']['mappings'].append({'type':'special','options':{'match':'null','result':{'text':'Unknown / No data','color':'#8e8e8e'}}})
    if kind=='table' and not states:result['fieldConfig']['defaults']['color']={'mode':'fixed','fixedColor':'text'}
    if link:
        result['fieldConfig']['defaults']['links']=[{'title':'Open '+title,'url':link,'targetBlank':False}]
    if kind=='table': result['options']={'showHeader':True,'cellHeight':'sm','footer':{'show':False}}
    return result


def mesh_query():
    # Both observed endpoints count. LLDP retains the last-known neighbor when down.
    base = '(max by (source,interface) (nexus_interfaces_vdcId{job="$switch_job",operSt="up"}) or (0 * max by (source,interface) (nexus_interfaces_vdcId{job="$switch_job"})))'
    joined = base + ' * on(source,interface) group_left(sysName) max by(source,interface,sysName) (nexus_lldp_id{job="$switch_job"})'
    # Filter at LLDP, not on an arbitrary expression (PromQL disallows that).
    a = joined.replace('nexus_lldp_id{job="$switch_job"}', 'nexus_lldp_id{job="$switch_job",source=~"VCCUnit.*",sysName=~"FSPUnit.*-switch"}')
    b = joined.replace('nexus_lldp_id{job="$switch_job"}', 'nexus_lldp_id{job="$switch_job",source=~"FSPUnit.*",sysName=~"VCCUnit.*-switch"}')
    a = 'label_replace(label_replace(('+a+'),"vcc","$1","source","(VCCUnit[0-9]+)-switch"),"fsp","$1","sysName","(FSPUnit[0-9]+)-switch")'
    b = 'label_replace(label_replace(('+b+'),"vcc","$1","sysName","(VCCUnit[0-9]+)-switch"),"fsp","$1","source","(FSPUnit[0-9]+)-switch")'
    return 'min by(vcc,fsp) ('+a+' or '+b+')'


DEFAULT_VCC = 4
DEFAULT_FSP = 3

def validate_placement(items):
    occupied = set()
    identities = set()
    for item in items:
        if item['id'] in identities: raise ValueError('Duplicate hardware identity')
        identities.add(item['id'])
        if item['face'] not in ('front', 'rear'): raise ValueError('Invalid rack face')
        low, height = item['position_u'], item['height_u']
        if type(low) is not int or type(height) is not int or low < 1 or height < 1 or low + height > 43:
            raise ValueError('Placement outside 42U')
        for slot in range(low, low + height):
            key = (item['rack'], item['face'], slot)
            if key in occupied: raise ValueError('Overlapping rack placement')
            occupied.add(key)
    return occupied


def rack_panels(vcc, fsp):
    fixture = json.loads((ROOT/'placement.json').read_text())
    # The reviewed static fixture covers the reduced scope only. Larger query
    # fixtures do not imply invented physical expansion.
    items = [p for p in fixture['placements'] if int(p['unit'].split('Unit')[1]) <= (vcc if p['unit'].startswith('VCC') else fsp)]
    validate_placement(items)
    panels = [{'type':'text','title':'42U physical rack — SYNTHETIC fixture',
        'gridPos':{'x':0,'y':0,'w':24,'h':3},'options':{'mode':'markdown','content':fixture['label'] + '. Lowest U is position; multi-U boxes span occupied slots. Front face shown; NetBox paused. Hardware health is observed independently; absent readings remain Unknown.'}}]
    for elevation, (rack, face) in enumerate(sorted({(p['rack'],p['face']) for p in items})):
        base = elevation * 88 + 3
        for slot in range(42, 0, -1):
            panels.append({'type':'text','title':f'U{slot:02}', 'gridPos':{'x':0,'y':base+(42-slot)*2,'w':2,'h':2},'options':{'mode':'markdown','content':f'**{slot:02}**'}})
            if not any(p['position_u'] <= slot < p['position_u']+p['height_u'] for p in items if (p['rack'],p['face'])==(rack,face)):
                panels.append({'type':'text','title':f'U{slot:02} Empty', 'gridPos':{'x':2,'y':base+(42-slot)*2,'w':22,'h':2},'options':{'mode':'markdown','content':'Empty U — SYNTHETIC'}})
        for p in items:
            if (p['rack'],p['face']) != (rack,face): continue
            server=p['kind']=='server'
            low=p['position_u']; high=low+p['height_u']-1
            title=f"{rack} {face} U{low:02}–{high:02} · {p['height_u']}U illustrative {p['kind']} · {p['id']}"
            expr=health(p['unit'],p['fhs']) if server else 'min('+interface_state(p['id'])+')'
            link=url('fhs',unit=p['unit'],fhs=p['fhs'],instance='All',node_instance='All') if server else url('switch',unit=p['unit'],switch=p['id'])
            panels.append(panel(title,expr,2,base+(42-high)*2,22,p['height_u']*2,link=link,states={0:('Healthy','green'),1:('Degraded','orange'),2:('Failed','red')} if server else {0:('Down','red'),1:('Up','green')}))
    return panels


def legacy_build(vcc=DEFAULT_VCC, fsp=DEFAULT_FSP):
    if not 1 <= vcc <= 24 or not 3 <= fsp <= 27: raise ValueError('Supported counts: VCC 1..24, FSP 3..27')
    dashboards = {}
    for key,(name,uid) in DEST.items():
        dashboards[key]={'uid':uid,'title':name,'schemaVersion':39,'version':1,'tags':['fhs-infrastructure','emulated-topology'], 'timezone':'browser','time':{'from':'now-15m','to':'now'},'refresh':'30s','editable':True,'templating':{'list':variables()},'links':[{'title':n,'url':url(k),'type':'link','targetBlank':False} for k,(n,_) in DEST.items() if k!=key], 'panels':[]}
    dashboards['rack']['panels']=rack_panels(vcc,fsp)
    mesh=panel('VCC to FSP connectivity',mesh_query(),0,0,24,25,kind='table',states={0:('Down','red'),1:('Up','green')})
    mesh['fieldConfig']['defaults']['custom']={'width':60,'align':'center','cellOptions':{'type':'color-background'}}
    mesh['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':'vcc\\fsp'},'properties':[{'id':'custom.width','value':110}]})
    mesh['transformations']=[{'id':'groupingToMatrix','options':{'columnField':'fsp','rowField':'vcc','valueField':'Value'}}]
    # Cell value is state; row identifies VCC and the field name identifies FSP.
    for i in range(1,fsp+1):
        port=f'eth1/{(i-1)//4+1}/{(i-1)%4+1}'
        mesh['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':f'FSPUnit{i}'},'properties':[{'id':'displayName','value':f'FSP {i}'},{'id':'links','value':[{'title':f'Open VCC interface to FSP Unit {i}','url':url('interface',interface=port,dynamic={'switch':'${__data.fields[0]:percentencode}-switch','unit':'${__data.fields[0]:percentencode}'})}]},{'id':'custom.cellOptions','value':{'type':'color-background'}}]})
    dashboards['mesh']['panels']=[mesh]
    server=dashboards['fhs']['panels']
    server.append({'type':'text','title':'FHS telemetry semantics','gridPos':{'x':0,'y':0,'w':24,'h':3},'options':{'mode':'markdown','content':'Observed FHS / Node Exporter readings. Gray means missing data; no replacement zeroes. PSU fan flag 1 = fault under the emulator contract. One PSU fault makes the unit Degraded. All native readings must cover every member before hardware health is Healthy. Temperature limits 70/85 C and fan limits 4000/1000 RPM are illustrative. Other status flags are raw readings, with unverified meanings.'}})
    server.append(panel('Server hardware health',health('$unit','$fhs'),0,3,24,3,states={0:('Healthy','green'),1:('Degraded','orange'),2:('Failed','red')}))
    y=6
    for component in json.loads((ROOT/'components.json').read_text()):
        server.append({'type':'row','title':component['title'],'collapsed':False,'gridPos':{'x':0,'y':y,'w':24,'h':1}});y+=1
        if component['title'].startswith('PSU '):
            i=component['title'][-1]
            expr=reading_query({'name':f'sts_psu{i}_fan'},component['source'])
            status=panel(component['title']+' health',expr,0,y,4,5,states={0:('Healthy','green'),1:('Fault','red')})
        else:
            status=panel(component['title']+' health',component_health(component),0,y,4,5,states={0:('Healthy','green'),1:('Degraded','orange'),2:('Failed','red')})
        server.append(status)
        readings=component['readings']
        for ix,r in enumerate(readings):
            column=ix%3;row=ix//3
            rp=panel(r['label'],reading_query(r,component['source']),4+column*6,y+row*4,6,4,kind='stat')
            rp['fieldConfig']['defaults']['unit']=r.get('unit','short')
            rp['options']['textMode']='value'
            rp['options']['colorMode']='none'
            # Raw flag/power/temperature numbers are not red just because they exceed 1.
            rp['fieldConfig']['defaults']['color']={'mode':'fixed','fixedColor':'text'}
            server.append(rp)
        y+=max(5,((len(readings)+2)//3)*4)
    server.append(panel('Network interfaces / aliases','node_network_info{job="$node_job",unit="$unit",fhs="$fhs",instance=~"$node_instance"}',0,y,24,8,kind='table'));y+=8
    for metric in ('node_network_carrier','node_network_mtu_bytes','node_network_speed_bytes'):
        server.append(panel(metric,metric+'{job="$node_job",unit="$unit",fhs="$fhs",instance=~"$node_instance"}',0,y,24,6,kind='table'));y+=6
    for metric in ('node_network_receive_bytes_total','node_network_transmit_bytes_total','node_network_receive_errs_total','node_network_transmit_errs_total'):
        server.append(panel(metric,'rate('+metric+'{job="$node_job",unit="$unit",fhs="$fhs",instance=~"$node_instance"}[$__rate_interval])',0,y,24,6,kind='timeseries'));y+=6
    switches=dashboards['switch']['panels']
    switches.append(panel('Selected switch interfaces',interface_state('$switch'),0,0,24,18,kind='table',link=url('interface',dynamic={'interface':'${__data.fields.interface:percentencode}'}),states={0:('Down','red'),1:('Up','green')}))
    switches.append(panel('Last-known LLDP neighbors','nexus_lldp_id{job="$switch_job",source="$switch"}',0,18,24,12,kind='table',link=url('interface',dynamic={'interface':'${__data.fields.interface:percentencode}'})))
    details=dashboards['interface']['panels']
    details.append(panel('Interface operational state',interface_state('$switch',True),0,0,8,5,states={0:('Down','red'),1:('Up','green')}))
    details.append(panel('Last-known peer','label_replace(nexus_lldp_id{job="$switch_job",source="$switch",interface="$interface",sysName=~".*-switch"},"peer_unit","$1","sysName","(.*)-switch")',0,5,24,8,kind='table',link=url('interface',dynamic={'unit':'${__data.fields.peer_unit:percentencode}','switch':'${__data.fields.sysName:percentencode}','interface':'${__data.fields.portIdV:percentencode}'})))
    peer=details[-1]
    peer['transformations']=[{'id':'organize','options':{
        'excludeByName':{'Time':True,'__name__':True,'Value':True,'capability':True,'chassisIdV':True,'chassisIdT':True,'dn':True,'job':True,'instance':True,'source':True,'peer_unit':True,'portIdT':True},
        'indexByName':{'sysName':0,'portIdV':1,'interface':2,'mgmtIp':3},
        'renameByName':{'interface':'Local interface'}}}]
    peer['fieldConfig']['defaults']['custom']={'minWidth':180,'width':260}
    details.append(panel('Raw interface metadata','nexus_interfaces_vdcId{job="$switch_job",source="$switch",interface="$interface"}',0,13,24,8,kind='table'))
    for ix,(metric,title) in enumerate([('nexus_interfaces_octets','Interface traffic (bytes/s)'),('nexus_interfaces_cRCAlignErrors','CRC / alignment errors (per second)'),('nexus_interfaces_dropEvents','Drop events (per second)')]):
        expr='rate('+metric+'{job="$switch_job",source="$switch",interface="$interface"}[$__rate_interval])'
        details.append(panel(title,expr,0,21+ix*6,24,6,kind='timeseries'))
    details.append(panel('LLDP diagnostics','nexus_lldp_id{job="$switch_job",source="$switch",interface="$interface"}',0,39,24,10,kind='table'))
    for d in dashboards.values():
        for n,p in enumerate(d['panels'],1):p['id']=n
    return dashboards


def reading_query(reading, source):
    node=reading.get('node_job',False)
    labels='job="$'+('node_job' if node else 'job')+'",unit="$unit",fhs="$fhs",instance=~"$'+('node_instance' if node else 'instance')+'"'
    if source and not node:labels+=',source="'+source+'"'
    if reading.get('extra'):labels+=','+reading['extra']
    # Review note: shared node target up has no logical host labels; retain host scope on readings only.
    target_labels='job="$node_job",instance=~"$node_instance"' if node else labels.split(',source=')[0].split(',chip=')[0].split(',device=')[0]
    return reading['name']+'{'+labels+'} and on(job,instance) (up{'+target_labels+'} == 1)'


def component_health(component):
    # Healthy requires all displayed primary readings; no absent -> zero fallback.
    known=[];warning=[];failed=[]
    for r in component['readings']:
        value='max('+reading_query(r,component['source'])+')'
        known.append('('+value+' == '+value+')')
        if r.get('kind')=='temperature':
            warning.append('('+value+' >= 70)');failed.append('('+value+' >= 85)')
        if r.get('kind')=='fan':
            warning.append('('+value+' < 4000)');failed.append('('+value+' < 1000)')
    complete=' and on() '.join(known)
    branches=[]
    if failed:branches.append('(vector(2) and on() ('+' or on() '.join(failed)+'))')
    if warning:branches.append('(vector(1) and on() ('+' or on() '.join(warning)+') and on() ('+complete+'))')
    branches.append('(vector(0) and on() ('+complete+'))')
    return ' or on() '.join(branches)


def interface_state(source, selected=False):
    sel='job="$switch_job",source="'+source+'"'+(',interface="$interface"' if selected else '')
    return '(max by(source,interface) (nexus_interfaces_vdcId{'+sel+',operSt="up"}) or (0 * max by(source,interface) (nexus_interfaces_vdcId{'+sel+'})))'


def build(vcc=DEFAULT_VCC, fsp=DEFAULT_FSP):
    import importlib.util
    from types import SimpleNamespace
    spec=importlib.util.spec_from_file_location("exact",ROOT/"exact.py")
    exact=importlib.util.module_from_spec(spec);spec.loader.exec_module(exact)
    return exact.build(SimpleNamespace(**globals()),legacy_build(vcc,fsp))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--vcc',type=int,default=DEFAULT_VCC);parser.add_argument('--fsp',type=int,default=DEFAULT_FSP);parser.add_argument('--output',type=Path,default=ROOT/'generated');args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    for k,d in build(args.vcc,args.fsp).items():(args.output/(k+'.json')).write_text(json.dumps(d,indent=2)+'\n')

if __name__=='__main__':main()
