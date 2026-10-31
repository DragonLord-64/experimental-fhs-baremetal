from pathlib import Path
import tempfile,subprocess,os,json,ssl,threading,http.server,hashlib,shutil
repo=Path(__file__).resolve().parents[3]
ansible=shutil.which('ansible-playbook')
assert ansible, 'Put ansible-playbook on PATH first'
class Handler(http.server.BaseHTTPRequestHandler):
 def do_HEAD(self):
  if self.path=='/downgrade': self.send_response(302);self.send_header('Location',f'http://localhost:{self.server.redirect_port}/');self.end_headers()
  else:self.send_response(200);self.end_headers()
 def log_message(self,*args):pass
with tempfile.TemporaryDirectory(prefix='fhs-preflight-') as folder:
 root=Path(folder); keys=root/'keys';keys.mkdir();(keys/'synthetic.pub').write_text('public fixture only\n')
 cert=root/'ca.crt';key=root/'key.pem'
 subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(key),'-out',str(cert),'-days','1','-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost'],capture_output=True,check=True)
 plain=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
 threading.Thread(target=plain.serve_forever,daemon=True).start()
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
 server.redirect_port=plain.server_port
 ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(cert,key);server.socket=ctx.wrap_socket(server.socket,server_side=True)
 threading.Thread(target=server.serve_forever,daemon=True).start()
 sdk=root/'sdk fixture.deb'
 subprocess.run(['python3',str(repo/'ops/role-tests/user-environments/make_sdk_fixture.py'),str(sdk)],capture_output=True,check=True)
 creds=root/'credentials.yml';creds.write_text('filebeat_elasticsearch_username: fixture\nfilebeat_elasticsearch_password: NEVER-PRINT-THIS\n')
 inv=root/'inventory.yml';inv.write_text('all:\n  children:\n    device_roles_fpga-host-server:\n      hosts:\n        fixture:\n          ansible_connection: local\n          ansible_user: synthetic\n')
 port=server.server_port
 variables={'preflight_checks':['distribution','users','filebeat_setup','filebeat'],'preflight_timeout':2,'fhs_keys_dir':str(keys),'fhs_setup_user_environments':True,'fpga_update_bittware_sdk':True,'fpga_bittware_sdk_deb':str(sdk),'apt_cache_url':f'http://localhost:{port}','git_proxy_url':f'http://localhost:{port}','pip_index_url':f'https://localhost:{port}/','pip_ca_bundle':str(cert),'platform_ca_certificates':[{'src':str(cert),'name':'fixture'}],'filebeat_package_path':str(sdk),'filebeat_setup_credentials_file':str(creds),'filebeat_credentials_file':str(creds),'filebeat_elasticsearch_hosts':[f'https://localhost:{port}'],'filebeat_setup_ssl_certificate_authorities':[str(cert)],'filebeat_ssl_certificate_authorities':[str(cert)]}
 env=dict(os.environ,ANSIBLE_ROLES_PATH=str(repo/'roles'),ANSIBLE_LOCAL_TEMP=str(root/'ansible-local'),ANSIBLE_REMOTE_TEMP=str(root/'ansible-remote'),ANSIBLE_NOCOLOR='1',NO_PROXY='localhost,127.0.0.1',no_proxy='localhost,127.0.0.1')
 def run(name,updates=None,success=True):
  data=dict(variables);data.update(updates or {});config=root/'vars.json';config.write_text(json.dumps(data))
  result=subprocess.run([ansible,'-i',str(inv),str(repo/'playbooks/preflight.yml'),'-e','@'+str(config)],env=env,capture_output=True,text=True,timeout=90)
  output=result.stdout+result.stderr
  Path('/tmp/fhs-preflight-'+name+'.log').write_text(output)
  assert (result.returncode==0)==success,(name,output[-4500:])
  assert 'NEVER-PRINT-THIS' not in output,name
  if success:assert 'changed=0' in output,(name,output[-1200:])
  print('PASS',name)
 before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (creds,cert,key,sdk,keys/'synthetic.pub')}
 run('all')
 run('missing-artifact',{'preflight_checks':['users'],'fpga_bittware_sdk_deb':str(root/'missing.deb')},False)
 run('unknown-ca',{'preflight_checks':['distribution'],'pip_ca_bundle':''},False)
 run('development-http',{'pip_index_url':f'http://localhost:{plain.server_port}/','pip_allow_insecure_http':True,'pip_trusted_hosts':['localhost'],'pip_ca_bundle':'','platform_ca_certificates':[],'filebeat_elasticsearch_hosts':[f'http://localhost:{plain.server_port}'],'filebeat_setup_ssl_certificate_authorities':[],'filebeat_ssl_certificate_authorities':[]})
 run('http-unrelated-trust',{'preflight_checks':['distribution'],'pip_index_url':f'http://localhost:{plain.server_port}/','pip_allow_insecure_http':True,'pip_trusted_hosts':['other-host']},False)
 run('insecure-pip',{'preflight_checks':['distribution'],'pip_index_url':'http://localhost/'},False)
 run('http-redirect',{'preflight_checks':['distribution'],'pip_index_url':f'https://localhost:{port}/downgrade'},False)
 run('bootstrap',{'preflight_checks':['distribution'],'pip_ca_bundle':str(root/'not-yet-installed.crt'),'preflight_check_endpoints':False})
 run('filebeat-bootstrap',{'preflight_checks':['filebeat'],'filebeat_ssl_certificate_authorities':[str(root/'not-yet-installed.crt')],'preflight_check_endpoints':False})
 creds.write_text('filebeat_elasticsearch_password: NEVER-PRINT-THIS\n')
 run('bad-credentials',{'preflight_checks':['filebeat_setup']},False)
 creds.write_text('filebeat_elasticsearch_username: fixture\nfilebeat_elasticsearch_password: NEVER-PRINT-THIS\n')
 assert all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in before.items())
 print('PASS unchanged input hashes')
 server.shutdown()
 plain.shutdown()
