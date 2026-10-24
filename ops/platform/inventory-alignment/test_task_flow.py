"""Run actual discovery, compare and reconciliation tasks against synthetic REST.

No hardware or remote service is contacted. Ansible packaging and task retry /
ownership conditions execute unchanged; the HTTP boundary is an in-memory API.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

import yaml
from test_importer import NetBox, ASSETS, MODULES

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'playbooks/netbox'


class TaskFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        executable=shutil.which('ansible-playbook')
        if executable: cls.command=[executable]
        elif importlib.util.find_spec('ansible'): cls.command=[sys.executable,'-m','ansible.cli.playbook']
        else: raise unittest.SkipTest('Real ansible-core required for importer task execution')

    def setUp(self):
        self.api=NetBox(); self.requests=[]; self.failures=0
        self.maker=self.api.add('dcim/manufacturers/',name='BittWare',slug='bittware')
        self.dtype=self.api.add('dcim/device-types/',manufacturer=self.maker['id'],model='Chassis')
        self.device=self.api.add('dcim/devices/',name='old-server',serial='CHASSIS-001',device_type=self.dtype['id'],tags=[])
        self.api.add(ASSETS,serial='CHASSIS-001',status='used',device_type=self.dtype['id'],device=self.device['id'])
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                parsed=urlsplit(self.path); owner.requests.append(('GET',self.path))
                if owner.failures:
                    owner.failures-=1; self.send_response(503); self.end_headers(); self.wfile.write(b'{}'); return
                filters={k:v[0] for k,v in parse_qs(parsed.query).items()}
                for key in list(filters):
                    if key.endswith('_id') or key in ('id','limit','offset'): filters[key]=int(filters[key])
                response=owner.api.request('GET','https://synthetic.invalid'+parsed.path,params=filters)
                self.send_response(200); self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(json.dumps(response.json()).encode())
            def do_POST(self): self.mutation('POST')
            def do_PATCH(self): self.mutation('PATCH')
            def do_DELETE(self): self.mutation('DELETE')
            def mutation(self,method):
                owner.requests.append((method,self.path))
                data=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
                response=owner.api.request(method,'https://synthetic.invalid'+self.path,json=data)
                self.send_response(response.status_code); self.send_header('Content-Type','application/json');self.end_headers()
                if response.status_code!=204:self.wfile.write(json.dumps(response.json()).encode())
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop_server)
        self.temp=tempfile.TemporaryDirectory(prefix='fhs-task-flow-');self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.vars=dict(netbox_url='http://127.0.0.1:'+str(self.server.server_port),netbox_token='synthetic',
            netbox_validate_certs_default=True,netbox_auth='Token synthetic',netbox_api_retries=1,netbox_api_retry_delay=0,
            netbox_api_loop_pause=0,ansible_python_interpreter=sys.executable,
            bootstrap_chassis_serial='CHASSIS-001',facts=dict(hostname='renamed-server',product_serial='PRODUCT-001',distribution='Synthetic',distribution_version='1'),
            ansible_facts=dict(hostname='renamed-server'),resource_field_definitions={},resource_field_types={},resource_fields={},
            netbox_resource_fields={},hardware_fields={},discovered_components=[],server_info={},ip_ownership=[],mac_ownership=[],
            discovered_interfaces=[dict(name='eth0',mac='02:11:22:33:44:55',addresses=[dict(address='192.0.2.1',prefix=24)])],
            selected_primary_ipv4={},netbox_site='Synthetic',netbox_role='Server',netbox_device_type='Chassis',netbox_manufacturer='BittWare')

    def stop_server(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)

    def run_tasks(self,tasks,variables=None,success=True,check=False):
        (self.folder/'vars.json').write_text(json.dumps(dict(self.vars,**(variables or {}))))
        tasks=[{'ansible.builtin.set_fact':{'ansible_facts':{'hostname':'{{ facts.hostname }}'},'discovered_interfaces':'{{ discovered_interfaces }}'}},*tasks]
        (self.folder/'play.yml').write_text(yaml.safe_dump([dict(hosts='localhost',connection='local',gather_facts=False,vars_files=[str(self.folder/'vars.json')],tasks=tasks)],sort_keys=False))
        env=dict(os.environ,ANSIBLE_HOME=str(self.folder/'home'),ANSIBLE_LOCAL_TEMP=str(self.folder/'tmp'),
            ANSIBLE_LIBRARY=str(SOURCE/'library'),ANSIBLE_MODULE_UTILS=str(SOURCE/'module_utils'),
            ANSIBLE_FILTER_PLUGINS=str(SOURCE/'filter_plugins'),ANSIBLE_NOCOLOR='1',ANSIBLE_STDOUT_CALLBACK='default')
        result=subprocess.run([*self.command,'-i','localhost,',str(self.folder/'play.yml'),*(['--check'] if check else [])],
            cwd=self.folder,env=env,text=True,capture_output=True,timeout=45)
        if success:self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        else:self.assertNotEqual(0,result.returncode,result.stdout+result.stderr)
        return result.stdout+result.stderr

    def network(self,device_id=None,interface='eth0'):
        obj=dict(name=interface,device=dict(id=device_id or self.device['id'],name='old-server'))
        self.api.add('ipam/ip-addresses/',address='192.0.2.1/24',assigned_object=obj)
        self.api.add('dcim/mac-addresses/',mac_address='02:11:22:33:44:55',assigned_object=obj)

    def test_compare_accepts_rename_with_same_physical_device_and_network(self):
        self.network()
        output=self.run_tasks([{'ansible.builtin.import_tasks':str(SOURCE/'tasks/compare.yml')}],check=True)
        self.assertIn('renamed-server',output)
        self.assertTrue(any('?serial=CHASSIS-001' in path for _,path in self.requests))
        self.assertTrue(any('device_id='+str(self.device['id']) in path for _,path in self.requests))
        self.assertEqual([],self.api.writes)
        self.assertEqual('old-server',self.api.rows('dcim/devices/')[0]['name'])

    def test_compare_still_rejects_other_device_or_interface_ownership(self):
        for device_id,interface in ((999,'eth0'),(self.device['id'],'other-port')):
            for endpoint in ('ipam/ip-addresses/','dcim/mac-addresses/'):
                with self.subTest(device=device_id,interface=interface,endpoint=endpoint):
                    self.api.tables.pop('ipam/ip-addresses/',None);self.api.tables.pop('dcim/mac-addresses/',None)
                    self.network()
                    row=self.api.rows(endpoint)[0]
                    row['assigned_object']=dict(name=interface,device=dict(id=device_id,name='old-server'))
                    output=self.run_tasks([{'ansible.builtin.import_tasks':str(SOURCE/'tasks/compare.yml')}],success=False)
                    self.assertIn('An IP is ambiguous' if endpoint=='ipam/ip-addresses/' else 'A MAC is ambiguous',output)
                    self.assertEqual([],self.api.writes)

    def test_compare_rejects_hostname_serial_collision_before_network_reads(self):
        self.api.add('dcim/devices/',name='renamed-server',serial='OTHER-CHASSIS')
        self.run_tasks([{'ansible.builtin.import_tasks':str(SOURCE/'tasks/compare.yml')}],success=False)
        self.assertFalse(any('ip-addresses' in path or 'mac-addresses' in path for _,path in self.requests))
        self.assertEqual([],self.api.writes)

    def fpga_vars(self,raw):
        defaults=yaml.safe_load((SOURCE/'netbox_import.yml').read_text())[1]['vars']
        selected={key:value for key,value in defaults.items() if key.startswith('bootstrap_bittware_') or key=='bootstrap_fpga_interface_type'}
        selected.update(bootstrap_bittware_enabled=True,bootstrap_fpga_complete=True,
            bootstrap_bittware_card_list_argv=[sys.executable,'-c','print('+repr(raw)+')'],
            bootstrap_bittware_sdk_root='/tmp',bootstrap_bittware_venv='/tmp',hardware_command_path='/usr/bin',
            facts=dict(self.vars['facts'],hostname='old-server'))
        return selected

    def test_partial_sdk_record_aborts_before_absence_reconciliation(self):
        raw='IA-860M FPGA-0\n Index : 0\n Part Number : IA-860M\n BMC Version : 1\n Board missing serial\n Index : 1\n Part Number : IA-860M\n BMC Version : 1\n'
        bay=self.api.add('dcim/module-bays/',device=self.device['id'],name='FPGA CARD 1',position='1')
        old=self.api.add(MODULES,device=self.device['id'],module_bay=bay['id'],module_type=999,serial='KEEP-ME')
        asset=self.api.add(ASSETS,serial='KEEP-ME',module_type=999,module=old['id'],status='used')
        apply=yaml.safe_load((SOURCE/'tasks/apply.yml').read_text())
        sync=next(task for task in apply if task['name']=='Preview or apply FPGA modules and their three interfaces')
        output=self.run_tasks([{'ansible.builtin.import_tasks':str(SOURCE/'tasks/fpga.yml')},sync],self.fpga_vars(raw),success=False)
        self.assertIn('Incomplete FPGA inventory',output)
        self.assertEqual(old,self.api.tables[MODULES][old['id']]);self.assertEqual(asset,self.api.tables[ASSETS][asset['id']])
        self.assertEqual([],self.api.writes)

    def test_successful_empty_sdk_scope_reconciles_absence(self):
        self.api.tables['dcim/devices/'][self.device['id']]['name']='old-server'
        bay=self.api.add('dcim/module-bays/',device=self.device['id'],name='FPGA CARD 1',position='1')
        old=self.api.add(MODULES,device=self.device['id'],module_bay=bay['id'],module_type=999,serial='REMOVE-ME')
        asset=self.api.add(ASSETS,serial='REMOVE-ME',module_type=999,module=old['id'],status='used')
        apply=yaml.safe_load((SOURCE/'tasks/apply.yml').read_text())
        sync=next(task for task in apply if task['name']=='Preview or apply FPGA modules and their three interfaces')
        variables=self.fpga_vars('No cards detected');variables['bootstrap_fpga_empty_pattern']='^No cards detected$'
        self.run_tasks([{'ansible.builtin.import_tasks':str(SOURCE/'tasks/fpga.yml')},sync],variables)
        self.assertNotIn(old['id'],self.api.tables[MODULES]);self.assertIsNone(self.api.tables[ASSETS][asset['id']]['module'])

    def test_reconciliation_tasks_retry_transient_gateway_failure(self):
        cases=[('apply.yml','Reconcile physical chassis serial before hostname metadata'),
               ('apply.yml','Reconcile serial-bearing DDR5 and NVMe assets'),
               ('import_nexus.yml','Reconcile switch physical chassis asset'),
               ('import_nexus.yml','Reconcile serial-bearing installed modules and retained assets')]
        for filename,name in cases:
            with self.subTest(task=name):
                self.api.tables['dcim/devices/'][self.device['id']]['name']='old-server'
                tasks=yaml.safe_load((SOURCE/'tasks'/filename).read_text())
                task=next(child for parent in tasks for child in parent.get('block',[]) if child.get('name')==name)
                variables=dict(facts=dict(self.vars['facts'],hostname='old-server'),bootstrap_component_manufacturer='BittWare',
                    switch=dict(name='old-server',serial='CHASSIS-001',model='Chassis',modules=[],omissions=[],bays=[]),nexus_site='Synthetic',nexus_role='Server')
                # Cisco task deliberately uses its actual manufacturer argument.
                if filename=='import_nexus.yml':
                    self.api.tables['dcim/manufacturers/'][self.maker['id']]['name']='Cisco'
                else:self.api.tables['dcim/manufacturers/'][self.maker['id']]['name']='BittWare'
                self.failures=1
                output=self.run_tasks([task],variables)
                self.assertEqual(0,self.failures)
                self.assertIn('RETRYING',output)

    def test_retry_budget_zero_and_permanent_errors_do_not_loop(self):
        tasks=yaml.safe_load((SOURCE/'tasks/apply.yml').read_text())
        task=next(child for parent in tasks for child in parent.get('block',[]) if child.get('name')=='Reconcile physical chassis serial before hostname metadata')
        self.failures=1
        output=self.run_tasks([task],dict(netbox_api_retries=0),success=False)
        self.assertNotIn('RETRYING',output)
        self.assertEqual(0,self.failures)
        output=self.run_tasks([task],dict(bootstrap_chassis_serial='Default string'),success=False)
        self.assertNotIn('RETRYING',output)
        self.assertIn('Physical serial',output)
        self.assertEqual([],self.api.writes)
