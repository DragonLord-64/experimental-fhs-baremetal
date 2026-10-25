#!/usr/bin/env python3
"""Controller's native Ansible/API scenarios; synthetic tools, real delivered chart."""
import copy
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import uuid
import yaml

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT/'playbooks/netbox'
FIXTURES = Path(__file__).parent/'fixtures/discovery'


def require(value, label):
    if not value: raise AssertionError(label)


class Native:
    def __init__(self, base, token, work, report):
        self.base=base.rstrip('/'); self.token=token; self.work=Path(work); self.report=report
        self.prefix='SYN-DISC-'+uuid.uuid4().hex[:8]; self.report['fixture_prefix']=self.prefix
        self.count=0; self.devices={}; self.k=None
        self.fixtures=self.work/'fixtures'; self.fixtures.mkdir()
        salt=uuid.uuid4().hex[:6]
        for source in FIXTURES.iterdir():
            if source.suffix not in ('.txt','.json'): continue
            text=source.read_text().replace('SYN-',self.prefix+'-')
            # Unique synthetic MACs prevent ownership collisions on repeated runs.
            for i in range(1,5):
                text=text.replace(f'0200.0000.000{i}',f'02{salt[:2]}.{salt[2:]} .000{i}'.replace(' ',''))
                text=text.replace(f'02:00:00:00:00:0{i}',f'02:{salt[:2]}:{salt[2:4]}:{salt[4:]}:00:0{i}')
            (self.fixtures/source.name).write_text(text)
        self.env=dict(os.environ,ANSIBLE_LIBRARY=str(SOURCE/'library'),ANSIBLE_MODULE_UTILS=str(SOURCE/'module_utils'),
            ANSIBLE_FILTER_PLUGINS=str(SOURCE/'filter_plugins'),ANSIBLE_NOCOLOR='1',ANSIBLE_STDOUT_CALLBACK='default',
            ANSIBLE_LOCAL_TEMP=str(self.work/'ansible-tmp'),ANSIBLE_HOST_KEY_CHECKING='False',
            FHS_DISCOVERY_TOKEN=token,PYTHONDONTWRITEBYTECODE='1')
        self.fake_collection()

    def name(self, suffix): return self.prefix+'-'+suffix
    def check(self, value, label):
        require(value,label); self.report.setdefault('checks',{})[label]=True
        print('PASS: '+label,flush=True)

    def api(self,path,data=None,method='GET'):
        request=Request(self.base+'/api/'+path,method=method,data=json.dumps(data).encode() if data is not None else None,
            headers={'Authorization':('Bearer ' if self.token.startswith('nbt_') else 'Token ')+self.token,'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=40) as response:
                raw=response.read(); return json.loads(raw) if raw else None
        except Exception as error:
            raise RuntimeError('NetBox API '+method+' '+path.split('?')[0]+' failed: '+type(error).__name__) from None

    def rows(self,path,**filters):
        page=path+'?'+urlencode(dict(filters,limit=100)); result=[]
        while page:
            body=self.api(page); result+=body['results']; nxt=body.get('next')
            if nxt and not nxt.startswith(self.base+'/api/'): raise ValueError('Foreign pagination URL')
            page=nxt[len(self.base+'/api/'):] if nxt else None
        return result

    def one(self,path,**filters):
        rows=self.rows(path,**filters); require(len(rows)==1,'Expected unique '+path+' fixture'); return rows[0]

    def fake_collection(self):
        root=self.work/'collections'; plugin=root/'ansible_collections/cisco/nxos/plugins'; (plugin/'action').mkdir(parents=True)
        (plugin/'modules').mkdir()
        (plugin/'modules/nxos_command.py').write_text('DOCUMENTATION = """module: nxos_command\nshort_description: Synthetic read-only NX-OS command boundary\noptions:\n  commands:\n    type: raw\n"""\n')
        (plugin/'action/nxos_command.py').write_text('''import json
from pathlib import Path
from ansible.plugins.action import ActionBase
class ActionModule(ActionBase):
    _supports_check_mode = True
    _requires_connection = False
    def run(self, tmp=None, task_vars=None):
        v=task_vars; commands=self._task.args['commands']
        if isinstance(commands,str):commands=[commands]
        suffix=v['fixture_nexus']; folder=Path(v['fixture_directory']); result=[]
        names={'show inventory all | json':'inventory','show version | json':'version',
               'show interface transceiver | json':'optics','show lldp neighbors detail | json':'lldp'}
        for command in commands:
            if command not in names:raise ValueError('Unexpected fixture command')
            result.append((folder/('nexus-'+suffix+'-'+names[command]+'.json')).read_text())
        with open(v['fixture_nexus_commands'],'a') as log:log.write(json.dumps(commands)+'\\n')
        return dict(changed=False,stdout=result,stdout_lines=[r.splitlines() for r in result])
''')
        self.env['ANSIBLE_COLLECTIONS_PATH']=str(root)+':'+os.environ.get('ANSIBLE_COLLECTIONS_PATH',str(Path.home()/'.ansible/collections')+':/usr/share/ansible/collections')

    def play(self,tasks,variables=None,options=(),expected=True):
        self.count+=1; folder=self.work/('play-'+str(self.count)); folder.mkdir()
        variables=dict(variables or {},netbox_url=self.base,netbox_token="{{ lookup('env','FHS_DISCOVERY_TOKEN') }}",netbox_validate_certs=True,
                       ansible_python_interpreter=sys.executable,netbox_api_retries=0,netbox_api_retry_delay=0,netbox_api_loop_pause=0)
        plays=[dict(hosts='all',connection='local',gather_facts=False,vars_files=[str(SOURCE/'defaults.yml')],vars=variables,
                    module_defaults={'group/netbox.netbox.netbox':dict(netbox_url='{{ netbox_url }}',netbox_token='{{ netbox_token }}',validate_certs=True)},tasks=tasks)]
        play=folder/'play.yml';play.write_text(yaml.safe_dump(plays,sort_keys=False));play.chmod(0o600)
        # Scenario overrides have the same precedence as an operator's -e values;
        # shared vars_files otherwise override play vars (including SDK paths).
        overrides=folder/'overrides.yml';overrides.write_text(yaml.safe_dump(variables,sort_keys=False));overrides.chmod(0o600)
        result=subprocess.run(['ansible-playbook','-i',self.name('ACCESS-A')+',',str(play),'-e','@'+str(overrides),*options],env=self.env,cwd=folder,text=True,capture_output=True,timeout=180)
        log=folder/'private.log';log.write_text((result.stdout+result.stderr).replace(self.token,'<redacted>'));log.chmod(0o600)
        require((result.returncode==0)==expected,'Ansible scenario '+str(self.count)+' unexpected exit; inspect private log')
        return result.stdout

    def module(self,module,values,options=(),expected=True):
        arguments = dict(values)
        if module != 'fhs_bittware_probe':
            arguments.update(netbox_url='{{ netbox_url }}',netbox_token='{{ netbox_token }}',validate_certs=True)
        task={module:arguments, 'register':'outcome'}
        output=self.work/('module-'+str(self.count+1)+'.json')
        tasks=[task,{'ansible.builtin.copy':dict(content='{{ outcome | to_json }}',dest=str(output),mode='0600'), 'check_mode':False}]
        self.play(tasks,options=options,expected=expected)
        return json.loads(output.read_text()) if expected else None

    def snapshot(self):
        # Includes native/Inventory IDs and API timestamps so even a redundant
        # PATCH fails the no-writes/idempotence comparison; normalizes URLs only.
        result={}
        for kind in ('interfaces','modules','module-bays','inventory-items','power-ports'):
            result[kind]=[]
            for d in self.devices.values(): result[kind]+=self.rows('dcim/'+kind+'/',device_id=d['id'])
        result['devices']=[self.api('dcim/devices/'+str(d['id'])+'/') for d in self.devices.values()]
        result['assets']=[v for v in self.rows('plugins/inventory/assets/') if str(v.get('serial','')).startswith(self.prefix)]
        result['cables']=[v for v in self.rows('dcim/cables/') if self.prefix in json.dumps(v)]
        def stable(value):
            if isinstance(value,dict):return {k:stable(v) for k,v in value.items() if k not in ('url','display_url')}
            if isinstance(value,list):return [stable(v) for v in value]
            return value
        return stable(result)

    def setup(self):
        status=self.api('status/')
        self.check(status['netbox-version'].startswith('4.7.0') and status['plugins'].get('netbox_inventory')=='2.7.1', 'installed NetBox and Inventory versions')
        self.check('netbox_topology_views' in status['plugins'],'Topology Views plugin active')
        self.report['versions']={k:status[k] for k in ('netbox-version','plugins')}
        self.site=self.api('dcim/sites/',dict(name=self.name('SITE'),slug=self.name('site').lower()),'POST')
        self.role=self.api('dcim/device-roles/',dict(name=self.name('SERVER'),slug=self.name('server').lower(),color='123456'),'POST')
        self.maker=self.api('dcim/manufacturers/',dict(name=self.name('MAKER'),slug=self.name('maker').lower()),'POST')
        self.dtype=self.api('dcim/device-types/',dict(model=self.name('SERVER'),slug=self.name('server').lower(),manufacturer=self.maker['id'],u_height=2),'POST')
        self.rack=self.api('dcim/racks/',dict(site=self.site['id'],name=self.name('RACK'),u_height=42),'POST')
        for suffix in ('HOST-A','HOST-B','HOST-C','HOST-D','MGMT','PDU-A','PDU-B'):
            name=self.name(suffix)
            self.module('fhs_inventory_sync',dict(mode='device',device=name,serial=name+'-CHASSIS',manufacturer=self.maker['name'],model=self.dtype['model'],site=self.site['name'],role=self.role['name']))
            self.devices[suffix]=self.one('dcim/devices/',name=name)
        # Existing peers outside import selection are explicitly seeded synthetic
        # devices/interfaces; no collector is invented for the management switch.
        for index,suffix in enumerate(('HOST-A','HOST-B','HOST-C','HOST-D'),1):
            interface=self.api('dcim/interfaces/',dict(device=self.devices[suffix]['id'],name='enp1s0np0',type='other'),'POST')
            table=json.loads((self.fixtures/f'nexus-{"a" if index<3 else "b"}-lldp.json').read_text())
            rows=table['__readonly__']['TABLE_nbor_detail']['ROW_nbor_detail']
            value=next(r['port_id'] for r in rows if r['sys_name']==self.name(suffix)).replace('.','')
            mac=':'.join(value[i:i+2] for i in range(0,12,2))
            record=self.api('dcim/mac-addresses/',dict(mac_address=mac,assigned_object_type='dcim.interface',assigned_object_id=interface['id']),'POST')
            self.api('dcim/interfaces/'+str(interface['id'])+'/',dict(primary_mac_address=record['id']),'PATCH')
        for name in ('gigabitEthernet 1/0/11','gigabitEthernet 1/0/9','ten-gigabitEthernet 1/0/27'):
            self.api('dcim/interfaces/',dict(device=self.devices['MGMT']['id'],name=name,type='other'),'POST')
        for suffix,outlet in (('PDU-A','12'),('PDU-B','8')):
            self.api('dcim/power-outlets/',dict(device=self.devices[suffix]['id'],name=outlet),'POST')
        self.nexus_commands=self.work/'nexus-commands.jsonl'

    def nexus(self,options=()):
        result=[]
        for label in ('a','b'):
            output=self.work/('nexus-'+label+'.json')
            self.play([{'ansible.builtin.import_tasks':str(SOURCE/'tasks/import_nexus.yml')},
                {'ansible.builtin.copy':dict(content='{{ fhs_topology | to_json }}',dest=str(output),mode='0600'),'tags':['always'],'check_mode':False}],
                dict(fixture_nexus=label,fixture_directory=str(self.fixtures),fixture_nexus_commands=str(self.nexus_commands),
                     nexus_site=self.site['name'],nexus_role=self.role['name'],nexus_epld_command=''),options=options)
            observation=json.loads(output.read_text()); result.append(observation)
            if not options:self.devices['NEXUS-'+label.upper()]=self.one('dcim/devices/',name=self.name('NEXUS-'+label.upper()))
        return result

    def sdk(self):
        binary=self.work/'venv/bin';binary.mkdir(parents=True)
        (binary/'python3').symlink_to(sys.executable)
        package=binary/'synthetic_bwsdk.py';package.write_text('READY=True\n')
        self.sdk_log=self.work/'sdk-commands.jsonl'
        # The fixture's Python package must import, environment/root/user must
        # match and argv must be read-only. Missing dependencies fail --help.
        prelude='''import json,os,sys
from pathlib import Path
import synthetic_bwsdk
assert os.environ['BWSDK_ROOT']==__SDK_ROOT__
assert os.getuid()==__UID__
with open(__LOG__,'a') as log:log.write(json.dumps(dict(argv=sys.argv[1:],uid=os.getuid(),root=os.environ['BWSDK_ROOT'],path=os.environ['PATH']))+'\\n')
if '--help' in sys.argv:print('synthetic SDK help');sys.exit(0)
'''.replace('__SDK_ROOT__',repr(str(self.work))).replace('__UID__',str(os.getuid())).replace('__LOG__',repr(str(self.sdk_log)))
        card=prelude+"assert sys.argv[1:]==['-v','-i','USB']\nprint(Path("+repr(str(self.fixtures/'cards.txt'))+").read_text())\n"
        qsfp=prelude+"assert sys.argv[1:] in [['-c','0','-i','USB','display'],['-c','1','-i','USB','display']]\n"+"index=int(sys.argv[2])\nprint(Path("+repr(str(self.fixtures))+"+('/qsfp-photo.txt' if index==0 else '/qsfp-official.txt')).read_text())\n"
        for name,text in (('bw_card_list',card),('bw_qsfp_info',qsfp)):
            path=binary/name;path.write_text('#!'+sys.executable+'\n'+text);path.chmod(0o700)
        lldp=self.work/'lldpcli';lldp.write_text('#!'+sys.executable+'\nprint('+repr((self.fixtures/'linux-lldp.json').read_text())+')\n');lldp.chmod(0o700)
        self.collect_vars=dict(facts=dict(hostname=self.name('HOST-A'),user_id=getpass.getuser(),ansible_local={}),
            ansible_user=getpass.getuser(),fpga_bittware_user=getpass.getuser(),bittware_sdk_venv=str(binary.parent),fpga_bittware_sdk_root=str(self.work),
            bootstrap_lldp_argv=[str(lldp)],nic_ports=[],hardware_command_path='/usr/bin:/bin')
        self.binary=binary

    def collect_linux(self,options=()):
        output=self.work/'linux-observation.json'
        self.play([{'ansible.builtin.import_tasks':str(SOURCE/'tasks/fpga.yml')},
            {'ansible.builtin.import_tasks':str(SOURCE/'tasks/topology_linux.yml')},
            {'ansible.builtin.copy':dict(content='{{ {"observation": fhs_topology, "cards": desired_fpga_cards} | to_json }}',dest=str(output),mode='0600'),'tags':['always'],'check_mode':False}],
            self.collect_vars,options=options)
        return json.loads(output.read_text())

    def topology(self,observations,preview=False,options=(),pairs=None):
        return self.module('fhs_topology_sync',dict(observations=observations,preview=preview,endpoint_pairs=pairs or []),options=options)

    def run(self):
        self.setup(); self.sdk(); switches=self.nexus(); linux=self.collect_linux()
        self.check([len(o['neighbors']) for o in switches]==[3,4],'all seven LLDP observations pass real Nexus task/parser boundary')
        self.check([len(c['interfaces']) for c in linux['cards']]==[2,3], 'dynamic physical FPGA interfaces include Removed port and clipped report')
        sdk_log=[json.loads(s) for s in self.sdk_log.read_text().splitlines()]
        self.check(all(r['uid']==os.getuid() and r['root']==str(self.work) and r['path'].startswith(str(self.binary)+':') for r in sdk_log),
                   'actual SDK task runs configured venv root and BittWare user')
        host=self.name('HOST-A')
        self.module('fhs_fpga_sync',dict(device=host,cards=linux['cards']))
        for expected in ('C0-QSFP0','C0-QSFP1','C1-QSFP0','C1-QSFP1','C1-QSFP2'):
            self.one('dcim/interfaces/',device_id=self.devices['HOST-A']['id'],name=expected)
        observations=switches+[linux['observation']]
        before=self.snapshot()
        for preview,options in ((True,()),(False,('--check',))):
            result=self.topology(observations,preview,options)
            self.check(self.snapshot()==before,'topology '+('compare' if preview else 'check')+' performs no writes')
        result=self.topology(observations)
        network=[p for p in result['plan'] if p['object']=='cable']
        self.check(len(network)==8,'seven representative LLDP cables plus one exact physical FPGA DAC created')
        dac=[p['after'] for p in network if 'DAC exact' in p['after']['description']]
        self.check(len(dac)==1 and sorted([len(dac[0]['a_terminations']),len(dac[0]['b_terminations'])])==[1,2], 'repeated breakout lanes terminate one physical DAC cable')
        # Check every expected LLDP pair persisted, not merely a total count.
        expected=[]
        for switch in switches:
            for n in switch['neighbors']:
                local=self.one('dcim/interfaces/',device_id=self.one('dcim/devices/',name=switch['device'])['id'],name=n['local'])
                self.check(bool(local['cable']), 'LLDP link '+switch['device']+'/'+n['local']+' persisted')
                expected.append(local['cable']['id'])
        self.check(len(set(expected))==7,'seven distinct representative LLDP links preserved')
        item=self.one('dcim/inventory-items/',device_id=self.devices['HOST-A']['id'],name='C0-QSFP0 transceiver')
        detail=item['custom_fields']['fhs_module_observation']['reported']
        self.check(item['serial']==self.name('CABLE-B-2') and item['part_id']=='QDD-400G-PC01' and
            detail['vendor_rev']=='00' and detail['vendor_date']=='260826' and detail['cable_length']=='1' and detail['Present']=='Present', 'Inventory module metadata round-trip includes vendor part serial revision date length presence')
        asset=self.one('plugins/inventory/assets/',inventoryitem_id=item['id'])
        self.check(asset['serial']==item['serial'],'pluggable metadata is attached to an Inventory physical asset')
        empty=self.one('dcim/interfaces/',device_id=self.devices['HOST-A']['id'],name='C1-QSFP2')
        self.check(not self.rows('dcim/inventory-items/',device_id=self.devices['HOST-A']['id'],name='C1-QSFP2 transceiver') and empty['custom_fields']['fhs_port_observation']['present'] is False,'Removed QSFP interface exists independently of module presence')
        lanes=[self.one('dcim/interfaces/',device_id=self.devices['NEXUS-A']['id'],name=n) for n in ('Ethernet1/1/1','Ethernet1/1/2')]
        self.check(lanes[0]['module']['id']==lanes[1]['module']['id'] and lanes[0]['cable']['id']==lanes[1]['cable']['id'], 'native module and cable associate breakout lanes with one physical connector')
        # Access aliases are verified by the collected actual hostname. A peer
        # outside the selected scope can instead resolve via its unique port MAC.
        aliases=copy.deepcopy(observations)
        aliases[0]['neighbors'][1]['remote']=self.name('ACCESS-A')
        aliases[0]['neighbors'][2]['remote']=self.name('UNSELECTED-ACCESS-B')
        alias_result=self.topology(aliases)
        self.check(not alias_result['changed'] and not any('unresolved' in s for s in alias_result['omissions']), 'verified access alias and existing unselected peer MAC resolve without invented interfaces')
        stable=self.snapshot(); repeat=self.topology(observations)
        self.check(not repeat['changed'] and self.snapshot()==stable,'repeated native topology apply is unchanged')
        self.check(any('CABLE-C' in s for s in repeat['omissions']), 'unverified same-prefix suffix serials remain unresolved')
        # A specific verified pair is supported; colliding rules cannot weaken it.
        mapping=dict(vendor='FS',part='QDD-400G-PC01',host_serial=self.name('CABLE-C-1'),switch_serial=self.name('CABLE-C'),evidence='Synthetic endpoint cross-check fixture only')
        result=self.topology(observations,pairs=[mapping,mapping])
        self.check(not result['changed'],'ambiguous endpoint pair rules preserve cables')
        result=self.topology(observations,pairs=[mapping])
        self.check(len([p for p in result['plan'] if p['object']=='cable'])==1,'explicit verified full endpoint pair creates only one additional DAC')
        self.check(not self.topology(observations,pairs=[mapping])['changed'],'verified endpoint pair apply is idempotent')
        # A different observed peer must not replace an already cabled link.
        conflict=copy.deepcopy(observations)
        conflict[0]['neighbors'][0]=dict(local='mgmt0',remote=self.name('HOST-A'),port='C1-QSFP2')
        snapshot=self.snapshot(); result=self.topology(conflict,pairs=[mapping])
        self.check(any('existing cable preserved' in s for s in result['omissions']) and self.snapshot()==snapshot,
                   'conflicting existing network cable preserved')
        # Failed, empty and partial reads never remove known modules/assets/ports.
        partial=copy.deepcopy(observations);partial[2]['ports'][0]['metadata']={'vendor_rev':'00'}
        result=self.topology(partial,pairs=[mapping]);self.check(not result['changed'],'partial module metadata preserves known fields')
        script=self.binary/'bw_qsfp_info';saved=script.read_text();script.write_text('#!'+sys.executable+'\nimport sys\nif "--help" in sys.argv: print("help");sys.exit(0)\nsys.exit(1)\n')
        failed=self.collect_linux(); self.module('fhs_fpga_sync',dict(device=host,cards=failed['cards']))
        self.topology(switches+[failed['observation']],pairs=[mapping]);script.write_text(saved)
        self.check(self.snapshot()==snapshot,'failed QSFP reads preserve interfaces cables Inventory metadata and asset IDs')
        # Exercise each read-only task route once; native compare/check above
        # already cover API write protection without repeating fixture lifecycles.
        initial=self.snapshot();self.nexus(('--tags','facts'));self.collect_linux(('--tags','compare'))
        self.check(self.snapshot()==initial,'actual facts and compare discovery tasks remain read-only')
        self.power_and_placement()
        final=self.snapshot();self.topology(observations,pairs=[mapping]);self.module('fhs_fpga_sync',dict(device=host,cards=linux['cards']))
        self.check(self.snapshot()==final,'repeated complete apply preserves all native and asset identities')
        self.report['topology_expected_pairs']=[list(pair) for pair in self.graph_pairs()]
        self.report['device_ids']=[d['id'] for d in self.devices.values()]
        self.report['network_cable_ids']=sorted({self.one('dcim/interfaces/',device_id=d['id'],name=n['name'])['cable']['id']
            for d in self.devices.values() for n in self.rows('dcim/interfaces/',device_id=d['id']) if n.get('cable')})

    def graph_pairs(self):
        pairs=set()
        for cable in self.rows('dcim/cables/'):
            if self.prefix not in json.dumps(cable):continue
            a=cable.get('a_terminations',[]);b=cable.get('b_terminations',[])
            for left in a:
                for right in b:
                    if left['object_type']==right['object_type']=='dcim.interface':
                        x=left.get('object',{}).get('device',{}).get('id');y=right.get('object',{}).get('device',{}).get('id')
                        if x and y:pairs.add(tuple(sorted((x,y))))
        return sorted(pairs)

    def power_and_placement(self):
        device=self.devices['HOST-A'];host=device['name']
        meta=dict(site=self.site['name'],role=self.role['name'],location=self.name('ROOM'),rack=self.rack['name'],rack_unit=12,power_ports=[
            dict(name='PSU1',pdu_serial=self.devices['PDU-A']['serial'],pdu_port='12'),dict(name='PSU2',pdu_serial=self.devices['PDU-B']['serial'],pdu_port='8')])
        info=self.work/'server-info.yaml';info.write_text(yaml.safe_dump(meta));original=info.read_bytes()
        self.play([{'ansible.builtin.import_tasks':str(SOURCE/'tasks/server_info.yml')},
            {'ansible.builtin.assert':dict(that=['server_info.rack_unit == 12','server_info.power_ports | length == 2'])}],dict(server_info_path=str(info)))
        self.check(info.read_bytes()==original,'actual server-info read validates schema and preserves existing file')
        params=dict(device=host,metadata=meta)
        initial=self.snapshot()
        for mode in ((True,()),(False,('--check',))):
            self.module('fhs_placement_sync',dict(params,preview=mode[0]),options=mode[1])
            self.check(self.snapshot()==initial,'placement/power '+str(mode)+' preview performs no writes')
        # Invalid second mapping must prevent the first inlet from being created.
        bad=copy.deepcopy(meta);bad['power_ports'][1]['pdu_serial']=self.name('MISSING')
        self.module('fhs_placement_sync',dict(params,metadata=bad),expected=False)
        self.check(self.snapshot()==initial,'missing PDU refuses entire placement/power operation before writes')
        # Schema/missing/ambiguous identity matrices remain in focused local
        # contracts; native coverage needs one invalid placement and occupancy.
        self.module('fhs_placement_sync',dict(params,metadata=dict(meta,rack_unit=0)),expected=False)
        self.check(self.snapshot()==initial,'invalid rack unit refused before writes')
        outlet=self.one('dcim/power-outlets/',device_id=self.devices['PDU-A']['id'],name='12')
        self.api('dcim/power-outlets/'+str(outlet['id'])+'/',dict(mark_connected=True),'PATCH')
        self.module('fhs_placement_sync',params,expected=False)
        self.api('dcim/power-outlets/'+str(outlet['id'])+'/',dict(mark_connected=False),'PATCH')
        self.check(self.snapshot()==initial,'occupied power outlet refused before placement or inlet creation')
        self.module('fhs_placement_sync',params)
        placed=self.api('dcim/devices/'+str(device['id'])+'/')
        self.check(float(placed['position'])==12 and placed['rack']['id']==self.rack['id'],'rack_unit persisted on native device')
        cable_ids=[]
        for inlet,pdu,outlet_name in (('PSU1','PDU-A','12'),('PSU2','PDU-B','8')):
            port=self.one('dcim/power-ports/',device_id=device['id'],name=inlet)
            outlet=self.one('dcim/power-outlets/',device_id=self.devices[pdu]['id'],name=outlet_name)
            self.check(port['cable']['id']==outlet['cable']['id'],inlet+' native cable reaches independently identified '+pdu)
            cable_ids.append(port['cable']['id'])
        self.check(len(set(cable_ids))==2,'PSU1 and PSU2 terminate distinct PDUs and cables')
        stable=self.snapshot();result=self.module('fhs_placement_sync',params)
        self.check(not result['changed'] and self.snapshot()==stable,'repeated placement/power apply unchanged')
        self.module('fhs_placement_sync',dict(device=host,metadata={}))
        self.check(self.snapshot()==stable,'missing new metadata preserves rack placement and power records')
        self.module('fhs_placement_sync',dict(params,metadata=dict(meta,rack_unit=14)),expected=False)
        bad=copy.deepcopy(meta);bad['power_ports']=[dict(name='PSU1',pdu_serial=self.devices['PDU-B']['serial'],pdu_port='8')]
        self.module('fhs_placement_sync',dict(params,metadata=bad),expected=False)
        self.check(self.snapshot()==stable,'existing placement and power cable conflicts preserved')
