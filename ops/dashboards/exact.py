"""Prototype geometry adapted to explicit lab inventory and observed telemetry.

Presentation constants classify inventory only; they never synthesize samples.
"""
import copy
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
GRAY='#555963'

def reference(name):return json.loads((ROOT/'references'/(name+'.json')).read_text())
def target(expr,legend='',ref='A',table=False):return {'refId':ref,'expr':expr,'instant':True,'range':False,'legendFormat':legend,**({'format':'table'} if table else {})}
def mapping(name,values):return {'matcher':{'id':'byName','options':name},'properties':[{'id':'mappings','value':[{'type':'value','options':{str(k):{'text':v[0],'color':v[1]} for k,v in values.items()}}]}]}
def element(name,x,y,w,h,text='',field=None,bg=None,size=11):
 e={'name':name,'type':'metric-value','placement':{'left':x,'top':y,'width':w,'height':h},'constraint':{'horizontal':'left','vertical':'top'},'config':{'align':'center','valign':'middle','size':size,'color':{'fixed':'#eeeeee'},'text':{'mode':'field' if field else 'fixed','field':field or '', 'fixed':text}}}
 if bg:e['background']={'color':bg}
 return e

def canvas(title,elements,targets,x,y,w,h):return {'type':'canvas','title':title,'gridPos':{'x':x,'y':y,'w':w,'h':h},'targets':targets,'fieldConfig':{'defaults':{'noValue':'TELEMETRY MISSING','color':{'mode':'fixed','fixedColor':GRAY}},'overrides':[]},'options':{'inlineEditing':False,'panZoom':False,'zoomToContent':True,'showAdvancedTypes':True,'root':{'name':'Root','type':'frame','elements':elements}}}
def note(text,y=0,h=2):return {'type':'text','title':'','transparent':True,'gridPos':{'x':0,'y':y,'w':24,'h':h},'options':{'mode':'markdown','content':text}}
def deployed(unit):return int(unit.split('Unit')[1]) <= (4 if unit.startswith('VCC') else 3)

def inventory():
 out=[]
 for rack in range(1,10):
  units=([f'VCCUnit{(rack-1)*4+i}' for i in range(1,5)] if rack<=6 else [])+[f'FSPUnit{(rack-1)*3+i}' for i in range(1,4)]
  slot=1
  for index,unit in enumerate(units):
   if index:slot+=1
   out.append({'rack':rack,'unit':unit,'id':unit+'-switch','kind':'switch','position_u':slot,'height_u':1,'face':'front','deployed':deployed(unit)});slot+=1
   for member in range(1,(1 if unit.startswith('VCC') else 4)+1):
    out.append({'rack':rack,'unit':unit,'id':unit+f'-FHS{member}','fhs':f'FHS{member}','kind':'server','position_u':slot,'height_u':1,'face':'front','deployed':deployed(unit)});slot+=1
 return out

def labelled(value, **labels):
    expr='vector('+str(value)+')'
    for key,value in labels.items():expr='label_replace('+expr+','+json.dumps(key)+','+json.dumps(str(value))+',"","")'
    return expr


def expected_host():
    """Explicit deployed membership, independent of exporter availability."""
    known=' or '.join(labelled(1,unit=p['unit'],fhs=p['fhs']) for p in inventory() if p['deployed'] and p['kind']=='server')
    return '('+labelled(1,unit='$unit',fhs='$fhs')+') and on(unit,fhs) ('+known+')'


def visual_hosts():
    """File authority, checked against the full inventory and all actual hosts."""
    hosts=json.loads((ROOT/'visual-inventory.json').read_text())
    identities=[(h['unit'],h['fhs']) for h in hosts]
    expected={(h['unit'],h['fhs']) for h in inventory() if h['kind']=='server' and not h['deployed']}
    if len(identities)!=116 or set(identities)!=expected:
        raise ValueError('Visual inventory must contain exactly the 116 nonemulated servers')
    return hosts


def visual_status(unit='$unit', fhs='$fhs'):
    # Separate raw identities, provenance and freshness; never accept actual hosts.
    hosts=visual_hosts()
    groups=[]
    for role in ('VCC','FSP'):
        units=sorted({h['unit'] for h in hosts if h['unit'].startswith(role)})
        members=sorted({h['fhs'] for h in hosts if h['unit'].startswith(role)})
        if {(u,f) for u in units for f in members} != {(h['unit'],h['fhs']) for h in hosts if h['unit'].startswith(role)}:
            raise ValueError('Visual inventory cannot be represented by disjoint role groups')
        groups.append('fhs_visual_status{job="node-emulator",origin="visual_fixture",unit="'+unit+'",fhs="'+fhs+'",unit=~"'+'|'.join(units)+'",fhs=~"'+'|'.join(members)+'"}')
    # timestamp must see original scrape samples: OR/reduction results carry
    # evaluation time and would make an old fixture appear perpetually fresh.
    fresh=['(('+raw+' == 0) and (time() - timestamp('+raw+') < 90))' for raw in groups]
    return 'max('+' or '.join(fresh)+')'


def visual_membership(unit='$unit', fhs='$fhs'):
    known=' or '.join(labelled(1,**h) for h in visual_hosts())
    return '('+labelled(1,unit=unit,fhs=fhs)+') and on(unit,fhs) ('+known+')'


def server_status(observed, unit='$unit', fhs='$fhs'):
    # Actual observations win. Unknown fixture data is not healthy inventory.
    expected=expected_host().replace('$unit',unit).replace('$fhs',fhs)
    return inventory_fallback('('+observed+') or on() ('+visual_status(unit,fhs)+')', '('+expected+') or on() ('+visual_membership(unit,fhs)+')')


def parent_inventory_state():
    """Inventory only: no observed parent hardware sensors exist in this contract."""
    known=' or '.join(labelled(1,source=p['id']) for p in inventory()
                      if p['kind']=='switch' and p['deployed'])
    selected='('+labelled(1,source='$switch')+') and on(source) ('+known+')'
    return '(3 * ('+selected+')) or on() vector(4)'


def expected_interface():
    known=' or '.join(labelled(1,source=source,interface=interface) for source,interfaces in json.loads((ROOT/'deployed-interfaces.json').read_text()).items() for interface in interfaces)
    return '('+labelled(1,source='$switch',interface='$interface')+') and on(source,interface) ('+known+')'


def expected_mesh():
    known=' or '.join(labelled(1,vcc='VCCUnit'+str(v),fsp='FSPUnit'+str(f)) for v in range(1,5) for f in range(1,4))
    return '('+labelled(1,vcc='VCCUnit$vccu',fsp='FSPUnit$fspu')+') and on(vcc,fsp) ('+known+')'


def inventory_fallback(observed, expected):
    # 3/4 are DISPLAY STATES only. Do not apply this to numeric sensor readings.
    return '('+observed+') or on() (3 * ('+expected+')) or on() vector(4)'


def classification(panel):
    """Keep absent inventory distinct from deployed but missing observations."""
    defaults=panel['fieldConfig']['defaults']
    mappings=defaults.setdefault('mappings',[])
    value=next((m for m in mappings if m['type']=='value'),None)
    if value is None:value={'type':'value','options':{}};mappings.append(value)
    value['options'].update({'3':{'text':'TELEMETRY MISSING','color':GRAY},'4':{'text':'NOT DEPLOYED','color':GRAY}})


def mesh_rate(direction):
    """Selected vccu endpoint only: separate RX/TX, never count peer twice."""
    counters='max by(source,interface) (rate(nexus_interfaces_octets{job="$switch_job",source="VCCUnit$vccu-switch",dn=~".*/dbgIfHC'+direction+'"}[5m]))'
    peer='max by(source,interface) (nexus_lldp_id{job="$switch_job",source="VCCUnit$vccu-switch",sysName="FSPUnit$fspu-switch"})'
    return 'sum(('+counters+') and on(source,interface) ('+peer+')) * 8 / 1e9'


def build(g,base):
 ds=g.DS
 dashboards=base
 dashboards['vlan']=copy.deepcopy(reference('vlan'))
 for key,d in dashboards.items():
  d.update(uid=g.DEST[key][1],title=g.DEST[key][0],tags=['fhs-infrastructure','explicit-lab-inventory'],refresh='30s')
  d['links']=[{'title':name,'url':g.url(k),'type':'link','targetBlank':False} for k,(name,uid) in g.DEST.items() if k!=key]
  d['templating']={'list':g.variables()}
  relevant={'rack':{'ds','job','switch_job'},'mesh':{'ds','switch_job','vccu','fspu'},'fhs':{'ds','job','node_job','unit','fhs'},'switch':{'ds','switch_job','switch','port'},'interface':{'ds','switch_job','switch','interface'},'vlan':{'ds','switch_job','vlan'}}[key]
  for v in d['templating']['list']:
   v['hide']=0 if v['name'] in relevant or v['name'].startswith('target_') else 2
   if v['name'].startswith('target_'):v['label']=v['name'][7:].upper()+' page'
  for k,count,label in [('vccu',24,'VCC unit'),('fspu',27,'FSP unit'),('port',32,'Physical port')]:
   d['templating']['list'].append({'name':k,'label':label,'type':'custom','query':','.join(map(str,range(1,count+1))),'current':{'text':'1','value':'1'},'hide':0 if k in relevant else 2})
  d['templating']['list'].append({'name':'vlan','label':'VLAN','type':'textbox','query':'55','current':{'text':'55','value':'55'},'hide':0 if key=='vlan' else 2})
  for v in d['templating']['list']:
   if v['name'] in ('unit','switch'):
    names=[f'{r}Unit{n}'+('-switch' if v['name']=='switch' else '') for r,count in [('VCC',24),('FSP',27)] for n in range(1,count+1)]
    v.update(type='custom',query=','.join(names),options=[]);v.pop('definition',None)
 # Rack elevations: explicit full inventory, one compact native Canvas per rack.
 rp=[note('**NINE 42U RACKS · SYNTHETIC PLACEMENT · devices 1U · one empty U between unit blocks** · 24 VCC + 27 FSP. 116 servers use **visual fixture** status: **not observed**. Switches outside the lab remain **NOT DEPLOYED**. Fixture feed missing/stale means unknown. **TELEMETRY MISSING** means deployed hardware without readings. Inventory persists when readings are unavailable.')]
 items=inventory()
 for rack in range(1,10):
  els=[];targets=[];over=[];occupied=set()
  for u in range(42,0,-1):els.append(element(f'U{u}',0,24+(42-u)*15,25,15,str(u),size=9))
  for p in [i for i in items if i['rack']==rack]:
   u=p['position_u'];height=p['height_u'];occupied.update(range(u,u+height));field=p['id']
   active=p['deployed'] or p['kind']=='server'
   txt=p['id']+(' · visual fixture / not observed' if not p['deployed'] and p['kind']=='server' else (' · NOT DEPLOYED' if not p['deployed'] else ''))
   el=element(field,29,24+(42-(u+height-1))*15,270,height*15-1,txt,field if active else None,{'field':field,'fixed':GRAY} if active else {'fixed':GRAY},10)
   if active:
    expr=(('('+g.health(p['unit'],p['fhs'])+') or on() vector(3)') if p['deployed'] else server_status(g.health(p['unit'],p['fhs']),p['unit'],p['fhs'])) if p['kind']=='server' else 'vector(3)'
    targets.append(target(expr,field,str(len(targets))))
    over.append(mapping(field,{0:(p['id']+(' · HEALTHY' if p['deployed'] else ' · ok · visual fixture / not observed'),'green'),1:(p['id']+' · DEGRADED','orange'),2:(p['id']+' · FAILED','red'),3:(p['id']+(' · TELEMETRY MISSING' if p['kind']=='server' else ' · HW UNKNOWN'),GRAY)}))
   el['links']=[{'title':'Open '+p['id'],'url':g.url('fhs',unit=p['unit'],fhs=p['fhs'],instance='All',node_instance='All') if p['kind']=='server' else g.url('switch',unit=p['unit'],switch=p['id']),'oneClick':True}];el['oneClickMode']='link';els.append(el)
  for u in range(42,0,-1):
   if u not in occupied:els.append(element('Empty'+str(u),29,24+(42-u)*15,270,14,'Empty',bg={'fixed':'#202226'},size=9))
  p=canvas(f'Rack {rack} · 42U front',els,targets,((rack-1)%3)*8,2+((rack-1)//3)*23,8,23);p['fieldConfig']['overrides']=over;rp.append(p)
 dashboards['rack']['panels']=rp
 # Keep the actual prototype's 648 fixed cell placements.
 mp=reference('mesh')['panels'];matrix=next(p for p in mp if p['type']=='canvas');matrix['targets']=[];matrix['fieldConfig']['overrides']=[]
 for e in matrix['options']['root']['elements']:
  name=e['name']
  if not (name.startswith('VCCU') and ' FSPU' in name):continue
  v=int(name[4:6]);f=int(name[-2:]);isdep=v<=4 and f<=3
  if not isdep:
   e['config']['text']={'mode':'fixed','fixed':'ND','field':''};e['background']={'color':{'fixed':GRAY}}
  else:
   expr='('+g.mesh_query()+f' and on(vcc,fsp) label_replace(label_replace(vector(1),"vcc","VCCUnit{v}","",""),"fsp","FSPUnit{f}","","")) or on() vector(3)'
   matrix['targets'].append(target(expr,name,str(len(matrix['targets']))))
   matrix['fieldConfig']['overrides'].append(mapping(name,{0:('fault','#F2495C'),1:('ok','#245F9B'),3:('?',GRAY)}))
  e['links']=[{'title':f'Inspect VCC{v} / FSP{f}','url':g.url('mesh',vccu=v,fspu=f),'oneClick':True}];e['oneClickMode']='link'
 matrix['title']='24 VCC × 27 FSP · 648 fixed links';matrix['fieldConfig']['defaults'].update(noValue='?',mappings=[])
 mp[0]=note('**VCC → FSP · 648 POTENTIAL LINKS** · ND = **NOT DEPLOYED** · ? = **TELEMETRY MISSING** · fault = observed link down · UP = observed link. Selected RX/TX rates are shown below. No traffic intensity is invented. Endpoint selectors affect details only.',h=3)
 counts=[('UP','count(('+g.mesh_query()+') == 1)'),('DOWN','count(('+g.mesh_query()+') == 0)'),('TELEMETRY MISSING','12 - count('+g.mesh_query()+')'),('NOT DEPLOYED','vector(636)')]
 for p,(title,expr) in zip(mp[1:5],counts):p['title']=title;p['targets']=[target(expr)]
 mp=mp[:6]
 selected=g.mesh_query()+' and on(vcc,fsp) label_replace(label_replace(vector(1),"vcc","VCCUnit$vccu","",""),"fsp","FSPUnit$fspu","","")'
 status=g.panel('VCC $vccu ↔ FSP $fspu · observed status',inventory_fallback(selected,expected_mesh()),0,24,8,3,states={0:('DOWN','red'),1:('UP','green')});classification(status);mp.append(status)
 rate_panel=g.panel('Observed throughput · RX / TX Gbit/s',mesh_rate('In'),8,24,8,3)
 rate_panel['targets']=[target(mesh_rate('In'),'RX'),target(mesh_rate('Out'),'TX','B')]
 rate_panel['fieldConfig']['defaults'].update(unit='suffix: Gbit/s',decimals=9)
 rate_panel['options'].update(textMode='value_and_name',colorMode='value')
 rate_panel['fieldConfig']['defaults']['color']={'mode':'fixed','fixedColor':'text'}
 rate_panel['description']='5m counter rates at selected vccu endpoint: RX received, TX transmitted. Peer endpoint is not counted again. Missing samples stay unknown, including on down links.'
 mp.append(rate_panel)
 capacity=g.panel('Link capacity · Gbit/s','vector(0) == 1',16,24,8,3)
 capacity['fieldConfig']['defaults']['unit']='suffix: Gbit/s';mp.append(capacity)
 mp.append(note('[Open selected VCC switch]('+g.url('switch',dynamic={'switch':'VCCUnit${vccu}-switch','unit':'VCCUnit${vccu}'})+') · Selected throughput is observed RX/TX at the vccu endpoint. Capacity and utilization remain unknown without configured/negotiated capacity.',27,2))
 dashboards['mesh']['panels']=mp
 # Compact two-column component rows with status square and grouped readings.
 components=json.loads((ROOT/'components.json').read_text());fp=[note('**FHS $unit / $fhs** · Status at left, observed readings at right. Nonemulated servers: **visual fixture / not observed** overall status only; component status and unsupported readings remain unknown. Gray = missing telemetry. Illustrative temperature70/85°C and fan4000/1000RPM limits. Native flag meanings need hardware validation.')]
 overall=g.panel('Overall hardware health',server_status(g.health('$unit','$fhs')),0,2,8,3,states={0:('Healthy','green'),1:('Degraded','orange'),2:('Failed','red')});classification(overall);fp.append(overall)
 for i,(title,expr) in enumerate([('Components',str(len(components))),('Deployed FHS','16'),('Visual fixture FHS','116')]):
  count=g.panel(title,'vector('+expr+')',8+i*5,2,5 if i<2 else 6,3);count['options']['colorMode']='value';count['fieldConfig']['defaults']['color']={'mode':'fixed','fixedColor':'#5794F2'};fp.append(count)
 for i,c in enumerate(components):
  x=(i%2)*12;y=5+(i//2)*3
  expr=g.reading_query({'name':'sts_psu'+c['title'][-1]+'_fan'},c['source']) if c['title'].startswith('PSU ') else g.component_health(c)
  sp=g.panel(c['title'],inventory_fallback(expr,"("+expected_host()+") or on() ("+visual_membership()+")"),x,y,2,3,states={0:('Healthy','green'),1:('Fault','red')} if c['title'].startswith('PSU ') else {0:('Healthy','green'),1:('Degraded','orange'),2:('Failed','red')});classification(sp);sp['title']='';sp['options']['textMode']='value';sp['options']['text']={'valueSize':11,'titleSize':10};fp.append(sp)
  readings=g.panel(c['title']+' · readings','vector(0) == 1',x+2,y,10,3);readings['targets']=[];readings['fieldConfig']['overrides']=[]
  for n,r in enumerate(c['readings']):
   readings['targets'].append(target(g.reading_query(r,c['source']),r['label'],chr(65+n)))
   readings['fieldConfig']['overrides'].append({'matcher':{'id':'byName','options':r['label']},'properties':[{'id':'unit','value':r.get('unit','short')},{'id':'decimals','value':r.get('decimals',1)}]})
  readings['options'].update(textMode='value_and_name',orientation='vertical',colorMode='value',text={'valueSize':17,'titleSize':10},wideLayout=False);readings['fieldConfig']['defaults']['color']={'mode':'fixed','fixedColor':'text'};fp.append(readings)
 y=5+((len(components)+1)//2)*3
 other=g.panel('Everything else · network / metadata','node_network_info{job="$node_job",unit="$unit",fhs="$fhs",instance=~"$node_instance"}',0,y,24,7,kind='table');other['transformations']=[{'id':'organize','options':{'excludeByName':{'Time':True,'__name__':True,'job':True,'instance':True},'indexByName':{'device':0,'ifalias':1,'address':2,'Value':3}}}];fp.append(other);dashboards['fhs']['panels']=fp
 # Exact 32-port/128-lane prototype Canvas, replacing mock measurements.
 sw=reference('switch')['panels'];sw[0]=note('**SWITCH $switch · 32 PHYSICAL PORTS / 128 SLOTS** · Link status comes from observations; fault reason: link down. Parent hardware and optic health remain Unknown without sensors. ND = **not deployed** (absent interface inventory); ? = **unknown** (missing telemetry). L1–L4 identify breakout lanes; full status is in interface details. Select port for optics below; click a lane for interface details.')
 board=sw[1];board['targets']=[target(parent_inventory_state(),'Parent inventory state')];board['fieldConfig']['overrides']=[mapping('Parent inventory state',{3:('unknown',GRAY),4:('not deployed',GRAY)})]
 inv=json.loads((ROOT/'deployed-interfaces.json').read_text())
 # Explicit inventory defaults distinguish missing observations from absent slots.
 for e in board['options']['root']['elements']:
  import re
  m=re.match(r'P(\d+)(?: L(\d+))?',e['name']);p=int(m[1]);lane=int(m[2]) if m[2] else None
  if lane:
   iface=f'eth1/{p}/{lane}';field=f'P{p} L{lane} state'
   if e['name'].endswith('link'):
    expr=g.interface_state('$switch').replace('source="$switch"','source="$switch",interface="'+iface+'"')
    expected=[]
    for source,interfaces in inv.items():
     if iface in interfaces:expected.append('label_replace(vector(3),"source","'+source+'","","")')
    if expected:
     gate='label_replace(vector(1),"source","$switch","","")'
     expr='('+expr+') or on() (('+ ' or '.join(expected)+') and on(source) '+gate+') or on() vector(2)'
    else:expr='('+expr+') or on() vector(2)'
    board['targets'].append(target(expr,field,str(len(board['targets']))));board['fieldConfig']['overrides'].append(mapping(field,{0:('fault','red'),1:('ok','green'),2:('ND','#c8cbd2'),3:('?','#c8cbd2')}))
   elif e['name'].endswith('quality'):e['config']['text']={'mode':'fixed','fixed':f'L{lane}','field':''}
   e['links']=[{'title':'Open '+iface,'url':g.url('interface',interface=iface,port=p),'oneClick':True}]
  else:
   if e['name'].endswith('health'):
    e['config']['text']={'mode':'field','fixed':'','field':'Parent inventory state'}
    e['placement']['left']-=36;e['placement']['width']+=36
    e['config']['color']={'fixed':'#ffffff'}
    e['config']['align']='center'
   if e['name'].endswith('link'):e['config']['text']={'mode':'fixed','fixed':'','field':''}
   if 'background' in e:e['background']={'color':{'fixed':'#444444' if p<=2 else '#34373d'}}
   e['links']=[{'title':f'Inspect port {p}','url':g.url('switch',port=p),'oneClick':True}]
  e['oneClickMode']='link'
  if e['type']=='rectangle':e['type']='metric-value';e['config']['text']={'mode':'fixed','fixed':'\u200b','field':''}
  if e['config']['text']['mode']=='fixed' and not e['config']['text'].get('fixed','').strip():e['config']['text']['fixed']='\u200b'
  if e['config']['text']['mode']=='fixed':e['config']['color']={'fixed':'#eeeeee'}
  e['placement']['left']=round(e['placement']['left']*.82);e['placement']['width']=round(e['placement']['width']*.82)
  e['placement']['top']=round(e['placement']['top']*.85);e['placement']['height']=round(e['placement']['height']*.85);e['config']['size']=10
 board['fieldConfig']['defaults']['noValue']='?'
 sw=sw[:2]
 # Unsupported optics are explicit unavailable values, never mock series.
 sw.append(note('**SELECTED PHYSICAL PORT $port · SHARED TRANSCEIVER** · identity / DOM unavailable in current emulator export. Hardware queries below use supplied Nexus field names and stay Unknown if absent.',16,2))
 for i,title in enumerate(['Transceiver identity / status','Optic temperature','Optic voltage','RX / TX optical power']):sw.append(g.panel(title,'vector(0) == 1',i*6,18,6,3))
 for i,(title,metric,unit) in enumerate([('Chassis temperature','nexus_ch_tempValue','celsius'),('PSU voltage / state','nexus_ch_volt','volt'),('Fans / hardware alarms · unavailable',None,'short')]):
  sp=g.panel(title,metric+'{job="$switch_job",source="$switch"}' if metric else 'vector(0) == 1',i*8,21,8,6,kind='table');sp['fieldConfig']['defaults']['unit']=unit;sp['transformations']=[{'id':'organize','options':{'excludeByName':{'Time':True,'__name__':True,'job':True,'instance':True},'indexByName':{'descr':0,'operSt':1,'Value':2}}}];sw.append(sp)
 sw.append(g.panel('Last-known LLDP neighbors','nexus_lldp_id{job="$switch_job",source="$switch"}',0,27,24,7,kind='table',link=g.url('interface',dynamic={'interface':'${__data.fields.interface:percentencode}'})))
 dashboards['switch']['panels']=sw
 # Existing detail has readable peer before raw metadata; tighten its vertical geometry.
 details=dashboards['interface']['panels'];details[0]['targets'][0]['expr']=inventory_fallback(details[0]['targets'][0]['expr'],expected_interface());classification(details[0]);details[0]['gridPos'].update(w=24,h=3)
 for p in details[1:]:p['gridPos']['y']-=2
 # VLAN configured allowance and explicit directed routes: unavailable is not empty configuration.
 vp=dashboards['vlan']['panels'];vp[0]=note('**VLAN $vlan · CONFIGURATION VIEW** · VCC left, FSP right. Allowed VLANs and explicit directed translations are unavailable in the lab. No direct, inverse or transitive allowance is inferred from LLDP or link state.')
 for p in vp[1:]:
  for t in p.get('targets',[]):t['expr']='vector(0) == 1'
  if 'fieldConfig' in p:p['fieldConfig']['defaults']['noValue']='Unknown / configuration unavailable'
 # Static inventory rows are explicitly labelled metadata, not VLAN observations.
 vp[1]['targets']=[target('vector(51)')];vp[1]['title']='Potential unit attachments'
 for p,role,count in [(vp[5],'VCC',24),(vp[6],'FSP',27)]:
  terms=[]
  for n in range(1,count+1):
   unit=f'{role}Unit{n}';dep=deployed(unit)
   labels={'Unit':f'{role} {n:02}','Deployment':'DEPLOYED' if dep else 'NOT DEPLOYED','Allowed VLANs':'Unknown' if dep else 'NOT DEPLOYED'}
   expr='vector(0)'
   for label,value in labels.items():expr='label_replace('+expr+','+json.dumps(label.replace(' ','_'))+','+json.dumps(value)+',"","")'
   terms.append(expr)
  p['targets']=[target(' or '.join(terms),table=True)]
  p['transformations']=[{'id':'organize','options':{'includeByName':{'Unit':True,'Deployment':True,'Allowed_VLANs':True},'indexByName':{'Unit':0,'Deployment':1,'Allowed_VLANs':2},'renameByName':{'Allowed_VLANs':'Allowed VLANs'}}}]
  p['fieldConfig']={'defaults':{'color':{'mode':'fixed','fixedColor':'text'},'custom':{'minWidth':120}},'overrides':[]}
 vp[-1]=g.panel('Explicit directed translation routes · unavailable','vector(0) == 1',0,25,24,7,kind='table')
 for d in dashboards.values():
  for i,p in enumerate(d['panels'],1):p['id']=i;p['datasource']=ds
 return canonical_presentation(dashboards)


def canonical_name(text):
    import re
    text=re.sub(r'(VCC|FSP)Unit(\d+)',lambda m:m[1].lower()+'u'+m[2],text)
    text=re.sub(r'FHS(\d+)',lambda m:'fhs'+m[1],text)
    text=text.replace('VCCU','vccu').replace('FSPU','fspu')
    return text.replace('VCC','vccu').replace('FSP','fspu')


def canonical_presentation(dashboards):
    import re
    """Translate presentation only; raw metric selectors and URL values stay native."""
    states={'Healthy':'ok','HEALTHY':'ok','Failed':'fault','FAILED':'fault',
            'Fault':'fault','Degraded':'degraded','DEGRADED':'degraded',
            'Up':'ok','UP':'ok','Down':'fault','DOWN':'fault',
            'TELEMETRY MISSING':'unknown','NOT DEPLOYED':'not deployed',
            'Unknown / No data':'unknown','Unknown / configuration unavailable':'unknown',
            'Unknown':'unknown','HW UNKNOWN':'unknown','HW ?':'unknown','ND':'ND','?':'?'}
    def visible(text):
        for old in sorted(states,key=len,reverse=True):
            text=text.replace(old,states[old])
        text=canonical_name(text)
        for name in ('unit','fhs','switch'):
            text=re.sub(r'\$'+name+r'\b', '${'+name+':text}', text)
        return text
    def markdown(text):
        # Markdown destinations carry native selector values and Grafana syntax.
        parts=re.split(r'(\]\([^\n]*?\))',text)
        return ''.join(part if part.startswith('](') else visible(part) for part in parts)
    def walk(obj):
        if isinstance(obj,list):
            for value in obj:walk(value)
        elif isinstance(obj,dict):
            for key,value in obj.items():
                if key in ('expr','url','query','definition','field','name','legendFormat'):
                    continue
                if isinstance(value,str) and key in ('title','label','text','fixed','content','noValue','displayName'):
                    obj[key]=markdown(value) if key=='content' else ('unknown' if key=='noValue' and value=='?' else visible(value))
                else:walk(value)
    for dashboard in dashboards.values():
        walk(dashboard)
        for variable in dashboard['templating']['list']:
            if variable['name'].startswith('target_'):
                uid=variable['current']['value']
                title=canonical_name(variable['current']['text'])+' ('+uid+')'
                variable['current']['text']=title
                variable['query']=title+' : '+uid
            if variable['name'] in ('unit','switch'):
                raw=variable['query'].split(',')
                variable['query']=','.join(canonical_name(v)+' : '+v for v in raw)
                variable['current']['text']=canonical_name(variable['current']['value'])
            elif variable['name']=='fhs':
                variable.update(type='custom',query=','.join('fhs'+str(i)+' : FHS'+str(i) for i in range(1,5)),options=[])
                variable.pop('definition',None)
                variable['current']['text']=canonical_name(variable['current']['value'])
        for panel in dashboard['panels']:
            if panel['type']=='table':
                # Display native identity labels canonically; links retain raw field values.
                defaults=panel['fieldConfig']['defaults']
                defaults.setdefault('mappings',[]).extend([
                    {'type':'regex','options':{'pattern':pattern,'result':{'text':text}}}
                    for pattern,text in [
                        ('^VCCUnit([0-9]+)-FHS([0-9]+)$','vccu$1-fhs$2'),
                        ('^FSPUnit([0-9]+)-FHS([0-9]+)$','fspu$1-fhs$2'),
                        ('^VCCUnit([0-9]+)(.*)$','vccu$1$2'),
                        ('^FSPUnit([0-9]+)(.*)$','fspu$1$2'),
                        ('^FHS([0-9]+)$','fhs$1')]])
        # Table label values are presentation metadata, not metric identities.
        if dashboard['uid']=='fhs-infra-vlan':
            for panel in dashboard['panels']:
                for target in panel.get('targets',[]):
                    import re
                    target['expr']=re.sub(r'"(VCC|FSP) (\d+)"',lambda m:'"'+m[1].lower()+'u'+str(int(m[2]))+'"',target['expr'])
                    target['expr']=target['expr'].replace('"NOT DEPLOYED"','"not deployed"').replace('"Unknown"','"unknown"').replace('"DEPLOYED"','"deployed"')
    # Compact symbols retain fixed prototype cells; the visible key explains them.
    mesh=dashboards['mesh']
    mesh['panels'][0]['options']['content']=('**vccu → fspu · 648 potential links** · '
        'ND = **not deployed** (absent inventory) · ? = **unknown** (missing telemetry) · '
        'ok = observed link · fault = observed link down. Selected RX/TX throughput below uses observed 5m counter rates. '
        'Endpoint selectors affect details only.')
    return dashboards
