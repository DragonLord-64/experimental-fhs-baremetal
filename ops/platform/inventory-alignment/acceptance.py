#!/usr/bin/env python3
"""Bounded synthetic REST + native Ansible module CLI acceptance on lab NetBox.

Inputs: --credentials /private/url-token.json --report /tmp/acceptance.json.
The service must be the delivered plugin image/chart. No hardware is contacted.
Fixtures remain for review; one unique run prefix prevents collisions on repeats.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode
import uuid

import yaml


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--credentials',required=True)
    parser.add_argument('--report',required=True)
    args=parser.parse_args()
    credentials=json.loads(Path(args.credentials).read_text())
    base=credentials['url'].rstrip('/')
    token=credentials['token']
    root=Path(__file__).resolve().parents[3]
    prefix='SYN-ALIGN-'+uuid.uuid4().hex[:8]
    checks=[]; report={'synthetic_only':True,'run':prefix,'base_url':base,'checks':checks,'snapshots':{}}
    def check(value,label):
        if not value: raise AssertionError(label)
        checks.append(label); print('PASS:',label,flush=True)
    def api(path,data=None,method='GET'):
        req=Request(base+'/api/'+path,method=method,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'Authorization':('Bearer ' if token.startswith('nbt_') else 'Token ')+token,'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=45) as response:
                body=response.read(); return json.loads(body) if body else None
        except HTTPError as e:
            raise RuntimeError(f'{method} {path}: HTTP {e.code}: {e.read().decode()}') from None
    def rows(path,**filters):
        result=[];page=path+'?'+urlencode(dict(filters,limit=100))
        while page:
            data=api(page);result.extend(data['results']);nxt=data.get('next')
            page=nxt.split('/api/',1)[1] if nxt else None
        return result
    def one(path,**filters):
        result=rows(path,**filters);check(len(result)==1,'Unique fixture '+path+' '+str(filters));return result[0]
    def module(name,expected=True,**values):
        env=dict(os.environ,ANSIBLE_LIBRARY=str(root/'playbooks/netbox/library'),
            ANSIBLE_MODULE_UTILS=str(root/'playbooks/netbox/module_utils'),
            ANSIBLE_LOCAL_TEMP=tempfile.mkdtemp(prefix='fhs-ansible-'),FHS_ACCEPT_TOKEN=token,
            ANSIBLE_NOCOLOR='1')
        values.update(netbox_url=base,netbox_token="{{ lookup('env', 'FHS_ACCEPT_TOKEN') }}",validate_certs=True)
        # The token is resolved by Ansible, never passed in command argv or report.
        command=['ansible','localhost','-i','localhost,','-c','local','-m',name,
                 '-e','ansible_python_interpreter='+os.environ.get('FHS_ANSIBLE_PYTHON',os.sys.executable),
                 '-a',json.dumps(values),'-o']
        result=subprocess.run(command,env=env,text=True,capture_output=True,timeout=90)
        if expected and result.returncode:
            raise AssertionError('Native '+name+' failed: '+result.stdout.replace(token,'<redacted>')+result.stderr.replace(token,'<redacted>'))
        if not expected: check(result.returncode!=0,'Ambiguous or missing physical identity refused by native CLI')
        return result
    A='plugins/inventory/assets/'; M='dcim/modules/'; I='dcim/inventory-items/'
    status=api('status/');report['status']=status
    check(status['netbox-version'].startswith('4.7.0'),'NetBox 4.7.0 API active')
    check(status['plugins'].get('netbox_inventory')=='2.7.1','Inventory 2.7.1 active')
    choices=api(A,method='OPTIONS')['actions']['POST']['status']['choices']
    check('faulty' in [v['value'] for v in choices],'Faulty choice active')
    maker=api('dcim/manufacturers/',{'name':prefix,'slug':prefix.lower()},'POST')
    site=api('dcim/sites/',{'name':prefix,'slug':prefix.lower()},'POST')
    role=api('dcim/device-roles/',{'name':prefix,'slug':prefix.lower()},'POST')
    dtype=api('dcim/device-types/',{'manufacturer':maker['id'],'model':prefix,'slug':prefix.lower()},'POST')
    dargs=dict(mode='device',device=prefix,serial=prefix+'-CHASSIS',manufacturer=prefix,model=prefix,site=prefix,role=prefix)
    module('fhs_inventory_sync',**dargs);device=one('dcim/devices/',serial=dargs['serial']);did=device['id']
    chassis=one(A,serial=dargs['serial']);module('fhs_inventory_sync',**dargs)
    check(one(A,serial=dargs['serial'])['id']==chassis['id'],'Chassis repeat retains asset ID')
    renamed=prefix+'-renamed'
    interface=api('dcim/interfaces/',{'device':did,'name':'eth0','type':'other'},'POST')
    suffix=prefix.rsplit('-',1)[1]
    mac='02:00:'+':'.join(suffix[n:n+2] for n in range(0,8,2))
    address='2001:db8:'+suffix[:4]+':'+suffix[4:]+'::1'
    assignment={'assigned_object_type':'dcim.interface','assigned_object_id':interface['id']}
    api('dcim/mac-addresses/',dict(assignment,mac_address=mac),'POST')
    api('ipam/ip-addresses/',dict(assignment,address=address+'/64'),'POST')
    with tempfile.TemporaryDirectory(prefix='fhs-live-compare-') as temporary:
        folder=Path(temporary)
        variables=dict(netbox_url=base,netbox_token="{{ lookup('env', 'FHS_ACCEPT_TOKEN') }}",
            netbox_auth="{{ ('Bearer ' if netbox_token.startswith('nbt_') else 'Token ') ~ netbox_token }}",
            netbox_validate_certs_default=True,netbox_api_retries=1,netbox_api_retry_delay=0,
            facts=dict(hostname=renamed,product_serial=dargs['serial'],distribution='Synthetic',distribution_version='1'),
            ansible_facts=dict(hostname=renamed),resource_field_definitions={},resource_field_types={},resource_fields={},
            netbox_resource_fields={},hardware_fields={},discovered_components=[],server_info={},ip_ownership=[],mac_ownership=[],
            discovered_interfaces=[dict(name='eth0',mac=mac,addresses=[dict(address=address,prefix=64)])],
            selected_primary_ipv4={},netbox_site=prefix,netbox_role=prefix,netbox_device_type=prefix,netbox_manufacturer=prefix)
        (folder/'vars.json').write_text(json.dumps(variables))
        tasks=[{'ansible.builtin.set_fact':{'ansible_facts':{'hostname':'{{ facts.hostname }}'},'discovered_interfaces':'{{ discovered_interfaces }}'}},
            {'ansible.builtin.import_tasks':str(root/'playbooks/netbox/tasks/compare.yml')}]
        (folder/'play.yml').write_text(yaml.safe_dump([dict(hosts='localhost',connection='local',gather_facts=False,
            vars_files=[str(folder/'vars.json')],tasks=tasks)],sort_keys=False))
        env=dict(os.environ,ANSIBLE_LIBRARY=str(root/'playbooks/netbox/library'),
            ANSIBLE_MODULE_UTILS=str(root/'playbooks/netbox/module_utils'),
            ANSIBLE_FILTER_PLUGINS=str(root/'playbooks/netbox/filter_plugins'),FHS_ACCEPT_TOKEN=token,
            ANSIBLE_HOME=str(folder/'home'),ANSIBLE_LOCAL_TEMP=str(folder/'tmp'),ANSIBLE_NOCOLOR='1',ANSIBLE_STDOUT_CALLBACK='default')
        result=subprocess.run(['ansible-playbook','-i','localhost,',str(folder/'play.yml'),'--check'],
            env=env,cwd=folder,text=True,capture_output=True,timeout=120)
        if result.returncode:raise AssertionError('Native compare failed: '+(result.stdout+result.stderr).replace(token,'<redacted>'))
        check('Stop before reassigning IPs' in result.stdout and 'Stop before reassigning MACs' in result.stdout,'Actual compare tasks accept serial-matched rename with assigned IP/MAC')
    check(one('dcim/devices/',serial=dargs['serial'])['name']==prefix,'Check-mode comparison preserves old hostname')
    module('fhs_inventory_sync',**dict(dargs,device=renamed))
    check(one('dcim/devices/',serial=dargs['serial'])['id']==did,'Hostname change preserves physical device ID')
    module('fhs_inventory_sync',expected=False,**dict(dargs,device=renamed,serial=''))
    def card(serial,kind='FPGA'):
        return {'bay':kind+' slot 1','position':'1','part':prefix+'-'+kind,'serial':serial,
            'interfaces':[{'name':prefix+'-'+kind+'-p'+str(n),'type':'other'} for n in range(3 if kind=='FPGA' else 1)]}
    for kind in ('FPGA','NIC'):
        oldserial=prefix+'-'+kind+'-old';newserial=prefix+'-'+kind+'-new'
        common=dict(device=renamed,kind=kind,manufacturer=prefix)
        module('fhs_fpga_sync',**common,cards=[card(oldserial,kind)])
        old=one(M,device_id=did,serial=oldserial);asset=one(A,serial=oldserial)
        before=rows('dcim/interfaces/',device_id=did,module_id=old['id'])
        if kind=='FPGA':
            peer=api('dcim/interfaces/',{'device':did,'name':prefix+'-synthetic-loopback-test','type':'other'},'POST')
            cable=api('dcim/cables/',{
                'a_terminations':[{'object_type':'dcim.interface','object_id':before[0]['id']}],
                'b_terminations':[{'object_type':'dcim.interface','object_id':peer['id']}],
                'status':'connected','description':'Synthetic refusal fixture only; not discovered cabling'},'POST')
            module('fhs_fpga_sync',expected=False,**common,cards=[card(newserial,kind)])
            check(one(M,device_id=did,serial=oldserial)['id']==old['id'] and one(A,serial=oldserial)['module']['id']==old['id'],'Real cabled FPGA replacement refuses without changing installation/asset')
            api('dcim/cables/'+str(cable['id'])+'/',method='DELETE')
            module('fhs_fpga_sync',expected=False,**common,cards=[card('',kind)],complete=True)
            check(one(M,device_id=did,serial=oldserial)['id']==old['id'],'Failed identified complete scan preserves existing installation')
        module('fhs_fpga_sync',**common,cards=[card(oldserial,kind)])
        check(one(A,serial=oldserial)['id']==asset['id'],'Repeat '+kind+' retains asset ID')
        module('fhs_fpga_sync',**common,cards=[card(newserial,kind)],preview=True)
        check(one(M,device_id=did,serial=oldserial)['id']==old['id'],'Preview '+kind+' preserves installed module')
        module('fhs_fpga_sync',**common,cards=[card(newserial,kind)])
        new=one(M,device_id=did,serial=newserial);retained=one(A,serial=oldserial)
        check(new['id']!=old['id'] and retained['id']==asset['id'] and retained['module'] is None and retained['status']=='stored',kind+' replacement retains stored old asset and creates installed record')
        after=rows('dcim/interfaces/',device_id=did,module_id=new['id'])
        check({i['id'] for i in before}=={i['id'] for i in after},kind+' interfaces survive replacement in place')
        module('fhs_fpga_sync',**common,cards=[],complete=False)
        check(one(M,device_id=did,serial=newserial)['id']==new['id'],'Incomplete '+kind+' scope preserves installation')
        module('fhs_fpga_sync',**common,cards=[],complete=True)
        check(not rows(M,device_id=did,serial=newserial) and one(A,serial=newserial)['module'] is None,'Complete empty '+kind+' removes installation and retains asset')
        history=rows('core/object-changes/',changed_object_type='netbox_inventory.asset',changed_object_id=asset['id'])
        check(len(history)>=2,kind+' retained real asset change log')
        report['snapshots'][kind]={'old_asset_id':asset['id'],'new_module_id':new['id'],'history_count':len(history)}
    comp=dict(name='DDR5 slot 1',kind='DDR5',part=prefix+'-DIMM',serial=prefix+'-DIMM-old')
    common=dict(mode='components',device=renamed,manufacturer=prefix)
    module('fhs_inventory_sync',**common,items=[comp]);old=one(I,device_id=did,name=comp['name']);asset=one(A,serial=comp['serial'])
    module('fhs_inventory_sync',**common,items=[comp]);check(one(A,serial=comp['serial'])['id']==asset['id'],'Component repeat retains asset')
    newcomp=dict(comp,serial=prefix+'-DIMM-new');module('fhs_inventory_sync',**common,items=[newcomp])
    check(one(I,device_id=did,name=comp['name'])['id']!=old['id'] and one(A,serial=comp['serial'])['inventoryitem'] is None,'Component replacement retains old asset')
    module('fhs_inventory_sync',**common,items=[],complete=False,scope=['DDR5']);check(bool(rows(I,device_id=did)),'Partial component scan preserves installations')
    module('fhs_inventory_sync',**common,items=[],complete=True,scope=['DDR5']);check(not rows(I,device_id=did),'Complete selected DDR5 empty scope removes installation')
    nexus=dict(bay='Ethernet1/1',model=prefix+'-DAC-local',manufacturer=prefix,serial=prefix+'-NEXUS-old',description='Synthetic local end; peer unknown')
    common=dict(mode='nexus',device=renamed)
    module('fhs_inventory_sync',**common,items=[nexus]);asset=one(A,serial=nexus['serial']);module('fhs_inventory_sync',**common,items=[nexus])
    check(one(A,serial=nexus['serial'])['id']==asset['id'],'Nexus repeat retains asset')
    module('fhs_inventory_sync',**common,items=[dict(nexus,serial=prefix+'-NEXUS-new')])
    check(one(A,serial=nexus['serial'])['module'] is None,'Nexus replacement retains old asset')
    module('fhs_inventory_sync',**common,items=[],complete=True,scope=[nexus['bay']])
    check(one(A,serial=prefix+'-NEXUS-new')['module'] is None,'Explicit Nexus bay absence retains asset')
    journal=rows('extras/journal-entries/',assigned_object_type='dcim.device',assigned_object_id=did)
    text=json.dumps(journal);check(all(v in text for v in (prefix+'-FPGA-old',prefix+'-FPGA-new','FPGA slot 1','installed','removed')),'Parent journal records old/new serial, bay and outcomes')
    report['journal_count']=len(journal)
    itype=api('plugins/inventory/inventory-item-types/',{'manufacturer':maker['id'],'model':prefix+'-standalone-DAC','slug':prefix.lower()+'-dac'},'POST')
    dac=api(A,{'inventoryitem_type':itype['id'],'serial':prefix+'-DAC','status':'stored'},'POST')
    api(A+str(dac['id'])+'/',{'status':'used'},'PATCH');api(A+str(dac['id'])+'/',{'status':'faulty'},'PATCH')
    dac=one(A,serial=prefix+'-DAC');history=rows('core/object-changes/',changed_object_type='netbox_inventory.asset',changed_object_id=dac['id'])
    check(dac['status']=='faulty' and dac['inventoryitem'] is None and len(history)>=3,'Standalone DAC stored/used/faulty history survives without fabricated cable link')
    report['device_id']=did;report['dac_asset_id']=dac['id'];report['checks_passed']=len(checks)
    Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    print(str(len(checks))+' checks passed; sanitized report '+args.report)


if __name__=='__main__': main()
