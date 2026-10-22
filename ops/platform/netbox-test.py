#!/usr/bin/env python3
"""Authenticated disposable object check and database pod-recreation persistence."""
import base64,json,socket,subprocess,time,urllib.request,urllib.error,uuid,sys,os,signal
from pathlib import Path
K=['minikube','-p','fhs-test','kubectl','--','--context=fhs-test','-n','fhs-platform','--request-timeout=30s']
def k(*args):return subprocess.check_output(K+list(args),text=True)
token=base64.b64decode(json.loads(k('get','secret','netbox-superuser','-o','json'))['data']['api_token']).decode()
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
pf=subprocess.Popen(K+['port-forward','--address=127.0.0.1','svc/netbox',f'{port}:80'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
base=f'http://127.0.0.1:{port}/netbox/api/'
def api(path,method='GET',data=None):
 req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Authorization':'Token '+token,'Content-Type':'application/json'},method=method)
 with urllib.request.urlopen(req,timeout=15) as r:return json.loads(r.read() or 'null')
def delete_owned(path):
 # Different app workers can retain old DB connections after the deliberate restart.
 # Only retry transient server errors; authentication/validation errors still fail.
 for attempt in range(30):
  try:
   api(path,'DELETE');return
  except urllib.error.HTTPError as error:
   if error.code==404:return
   if error.code<500 or attempt==29:raise
   time.sleep(2)
obj=None
try:
 for _ in range(60):
  try:api('status/');break
  except Exception:
   if pf.poll() is not None:raise RuntimeError('NetBox port-forward exited')
   time.sleep(1)
 else:raise RuntimeError('NetBox API did not become ready')
 name='fhs-check-'+uuid.uuid4().hex[:12]
 obj=api('dcim/sites/','POST',{'name':name,'slug':name,'status':'active'})
 path=f'dcim/sites/{obj["id"]}/'
 assert api(path)['name']==name
 # Read the object after the database process and its pod have been recreated.
 before=json.loads(k('get','pod','netbox-postgresql-0','-o','json'))['metadata']['uid']
 k('delete','pod','netbox-postgresql-0','--wait=true','--timeout=90s')
 k('wait','--for=condition=Ready','pod/netbox-postgresql-0','--timeout=240s')
 after=json.loads(k('get','pod','netbox-postgresql-0','-o','json'))['metadata']['uid']
 assert before!=after
 for _ in range(60):
  try:
   assert api(path)['name']==name;break
  except Exception:time.sleep(2)
 else:raise RuntimeError('NetBox object did not survive database pod recreation')
 if '--lifecycle' in sys.argv:
  os.killpg(pf.pid,signal.SIGTERM);pf.wait(timeout=10)
  lifecycle=str(Path(__file__).resolve().parents[1]/'kubernetes'/'lifecycle.sh')
  subprocess.run([lifecycle,'down'],check=True)
  subprocess.run([lifecycle,'up'],check=True)
  k('rollout','status','deploy/netbox','--timeout=360s')
  pf=subprocess.Popen(K+['port-forward','--address=127.0.0.1','svc/netbox',f'{port}:80'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  for _ in range(90):
   try:
    assert api(path)['name']==name;break
   except Exception:time.sleep(2)
  else:raise RuntimeError('NetBox object did not survive cluster down/up')
  print('PASS: NetBox database object retained across full cluster down/up')
 delete_owned(path);obj=None
 print('PASS: authenticated NetBox API create/read/delete and PostgreSQL pod-recreation persistence')
finally:
 if obj is not None:
  try:delete_owned(f'dcim/sites/{obj["id"]}/')
  except Exception:print('Cleanup incomplete: disposable NetBox site id',obj['id'])
 os.killpg(pf.pid,signal.SIGTERM)
 try:pf.wait(timeout=10)
 except subprocess.TimeoutExpired:os.killpg(pf.pid,signal.SIGKILL);pf.wait()
