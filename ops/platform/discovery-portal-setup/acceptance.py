#!/usr/bin/env python3
"""Supervised, isolated full-chart acceptance. Never called by the implementation worker.

The public entrypoint copies an allowlist of sources to dragonvm and runs there.
Only fhs-test/fhs-discovery-portal-test may be mutated. Evidence is retained;
credentials and port forwards are temporary. No successful result permits skips.
"""
import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

ROOT = Path(__file__).resolve().parents[3]
CONTEXT = 'fhs-test'
NAMESPACE = 'fhs-discovery-portal-test'
RELEASE = 'mid-cbf-hw'
PREFIX = '/mid-cbf-hw'
OWNER = 'discovery-portal-setup'
REQUIRED = {'preflight', 'baseline', 'native_baseline', 'upgrade', 'inventory_preserved',
            'native_final', 'discovery', 'routes', 'logging', 'idempotence', 'preservation'}


def run(argv, *, data=None, timeout=180, env=None):
    """Never echo command output: it can contain Secret material or API errors."""
    result = subprocess.run([str(v) for v in argv], input=data, capture_output=True,
                            timeout=timeout, env=env)
    if result.returncode:
        diagnostic = os.environ.get('FHS_ACCEPTANCE_DIAGNOSTICS')
        if diagnostic:
            folder = Path(diagnostic); folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = folder/(Path(str(argv[0])).name+'-'+uuid.uuid4().hex+'.log')
            path.write_bytes(result.stdout+b'\n'+result.stderr); path.chmod(0o600)
        raise RuntimeError('Command failed: '+Path(str(argv[0])).name+
                           ' (exit '+str(result.returncode)+'); output withheld')
    return result.stdout


def validate_scope(context, namespace):
    if context != CONTEXT or namespace != NAMESPACE:
        raise ValueError('Only --context fhs-test --namespace fhs-discovery-portal-test is authorized')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def stable_api(value):
    """Port-forward origins change between observations; inventory fields do not."""
    if isinstance(value, dict):
        return {k: stable_api(v) for k, v in value.items()}
    if isinstance(value, list):
        return [stable_api(v) for v in value]
    if isinstance(value, str):
        from urllib.parse import urlsplit
        url = urlsplit(value)
        if url.hostname in ('127.0.0.1', 'localhost') and url.path.startswith(PREFIX+'/netbox/'):
            return url.path+('?' + url.query if url.query else '')
    return value


def require(value, message):
    if not value:
        raise AssertionError(message)


def wait_for(function, label, seconds=180):
    deadline = time.monotonic()+seconds
    while True:
        try:
            result = function()
            if result:
                return result
        except (HTTPError, URLError, ConnectionError, TimeoutError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError('Timed out: '+label)
        time.sleep(3)


def request(url, data=None, method='GET', headers=None, allowed=(200, 201)):
    body = None if data is None else json.dumps(data).encode()
    hdr = {'Content-Type': 'application/json', **(headers or {})}
    try:
        with urlopen(Request(url, body, hdr, method=method), timeout=30) as response:
            code, content = response.status, response.read()
    except HTTPError as error:
        code, content = error.code, error.read()
    require(code in allowed, 'HTTP '+str(code)+' for '+method+' '+url.split('?')[0])
    if not content:
        return None
    try:
        return json.loads(content)
    except (ValueError, UnicodeDecodeError):
        return content.decode()


class Acceptance:
    def __init__(self, report):
        self.path = Path(report)
        self.evidence = {'status': 'failed', 'started_at': datetime.now(timezone.utc).isoformat(),
                         'context': CONTEXT, 'namespace': NAMESPACE, 'checks': {},
                         'limitations': ['Synthetic hardware fixtures; no physical hardware validation.',
                                         'Browser visual QA not performed; HTTP routes/assets checked.']}
        self.k = ['minikube', '-p', CONTEXT, 'kubectl', '--', '--context='+CONTEXT]
        self.work = Path(tempfile.mkdtemp(prefix='fhs-discovery-acceptance-'))
        self.work.chmod(0o700)
        self.evidence['evidence_directory'] = str(self.work)
        self.credentials = {}
        self.forwards = []

    def kubectl(self, *args, obj=None, namespace=True):
        command = self.k + (['-n', NAMESPACE] if namespace else []) + list(args)
        return run(command, data=json.dumps(obj).encode() if obj is not None else None, timeout=1000)

    def get(self, resource, name=None, namespace=True):
        return json.loads(self.kubectl('get', resource, *([name] if name else []), '-o', 'json', namespace=namespace))

    def apply(self, obj):
        self.kubectl('apply', '-f', '-', obj=obj)

    def record(self, name, details):
        require(name not in self.evidence['checks'], 'Duplicate check '+name)
        self.evidence['checks'][name] = details
        self.save()
        print('PASS: '+name, flush=True)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Report intentionally contains only explicitly selected fields, never raw command output.
        self.path.write_text(json.dumps(self.evidence, indent=2)+'\n')

    @contextmanager
    def forward(self, service, port):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); local = sock.getsockname()[1]
        proc = subprocess.Popen(self.k+['-n', NAMESPACE, 'port-forward', 'service/'+service,
                                str(local)+':'+str(port), '--address=127.0.0.1'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.forwards.append(proc)
        try:
            def connected():
                require(proc.poll() is None, 'Port forward exited')
                try:
                    with socket.create_connection(('127.0.0.1', local), timeout=1):
                        return True
                except OSError:
                    return False
            wait_for(connected, 'port forward '+service, 60)
            yield 'http://127.0.0.1:'+str(local)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
            self.forwards.remove(proc)

    def preflight(self):
        for tool in ('minikube', 'helm', 'ansible', 'ansible-playbook'):
            require(shutil.which(tool), 'Missing dependency '+tool)
        import yaml  # required by importer harnesses and Helm values
        import pynetbox  # same interpreter used by the native FRU apply fixture
        run(['ansible-doc', '-t', 'module', 'netbox.netbox.netbox_site'])
        nodes = self.get('nodes', namespace=False)['items']
        require(nodes and all(any(c['type']=='Ready' and c['status']=='True'
                                 for c in n['status']['conditions']) for n in nodes), 'Lab nodes not Ready')
        services = json.loads(self.kubectl('get', 'services', '-A', '-o', 'json', namespace=False))['items']
        pods = json.loads(self.kubectl('get', 'pods', '-A', '-o', 'json', namespace=False))['items']
        # Inspect capacity without restarting the cluster or touching another namespace.
        capacity = [{'name': n['metadata']['name'], 'allocatable': n['status']['allocatable']} for n in nodes]
        self.evidence['cluster_before'] = {'nodes': capacity,
            'services': [{'namespace': s['metadata']['namespace'], 'name': s['metadata']['name']} for s in services],
            'pod_count': len(pods)}
        namespaces = self.get('namespaces', namespace=False)['items']
        existing = next((n for n in namespaces if n['metadata']['name']==NAMESPACE), None)
        if existing:
            require(existing['metadata'].get('labels', {}).get('fhs-acceptance-owner')==OWNER,
                    'Namespace exists without this acceptance owner; refusing adoption')
            releases = json.loads(run(['helm', 'list', '--kube-context', CONTEXT, '-n', NAMESPACE, '-o', 'json']))
            require(not releases, 'Retained release exists: preserve evidence; use a reviewed namespace reset before fresh-install acceptance')
            require(not self.get('pvc')['items'], 'Retained PVCs exist; refusing destructive fresh install')
        else:
            self.apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE,
                        'labels': {'fhs-acceptance-owner': OWNER}}})
        source = json.loads((ROOT/'ops/platform/discovery-portal-setup/source-evidence.json').read_text())
        baseline = self.work/'baseline'; baseline.mkdir()
        for entry in source['archives']:
            archive = ROOT/'baselines'/entry['archive']
            require(archive.is_file() and hashlib.sha256(archive.read_bytes()).hexdigest()==entry['sha256'],
                    'Missing or mismatched committed baseline '+entry['source'])
            if entry['source']=='private':
                with tarfile.open(archive) as tar:
                    for member in tar.getmembers():
                        require(not member.name.startswith('/') and '..' not in Path(member.name).parts,
                                'Unsafe baseline archive')
                    tar.extractall(baseline, filter='data')
        self.baseline_chart = baseline/'platform/charts/fhs-platform'
        require((self.baseline_chart/'Chart.yaml').is_file(), 'Incomplete baseline chart')
        self.evidence['sources'] = source
        self.evidence['candidate_sha256'] = json.loads((ROOT/'candidate.json').read_text())
        self.record('preflight', {'ready_nodes': len(nodes), 'services_inspected': len(services),
                                  'namespace_owner': OWNER, 'baseline_hashes_verified': True})

    def values(self):
        # Replace the complete scrape_configs list before the FIRST install: no production traffic.
        return {'global': {'hostname': 'localhost', 'scheme': 'http', 'urlPrefix': PREFIX,
                           'discovery': {'enabled': False, 'refreshInterval': '5s'}},
                'netbox': {'persistence': {'storageClass': 'standard'},
                           'extraEnvs': [{'name': 'GRANIAN_EXTRA_ARGS', 'value': '--host=0.0.0.0'},
                                         {'name': 'GRANIAN_WORKERS', 'value': '1'}],
                           'resources': {'requests': {'cpu': '100m', 'memory': '384Mi'},
                                         'limits': {'cpu': '2', 'memory': '1536Mi'}},
                           'worker': {'resources': {'requests': {'cpu': '50m', 'memory': '128Mi'},
                                                    'limits': {'cpu': '1', 'memory': '512Mi'}}}},
                'postgresql': {'primary': {'persistence': {'storageClass': 'standard', 'size': '2Gi'},
                                          'resources': {'requests': {'cpu': '50m', 'memory': '128Mi'},
                                                        'limits': {'cpu': '1', 'memory': '384Mi'}}}},
                'valkey': {'primary': {'persistence': {'storageClass': 'standard'},
                                      'resources': {'requests': {'cpu': '25m', 'memory': '32Mi'},
                                                    'limits': {'cpu': '500m', 'memory': '128Mi'}}}},
                'grafana': {'persistence': {'storageClassName': 'standard'},
                            'resources': {'requests': {'cpu': '50m', 'memory': '128Mi'},
                                          'limits': {'cpu': '1', 'memory': '512Mi'}}},
                'prometheus': {'server': {'persistentVolume': {'storageClass': 'standard', 'size': '2Gi'},
                                          'resources': {'requests': {'cpu': '50m', 'memory': '128Mi'},
                                                        'limits': {'cpu': '1', 'memory': '512Mi'}}},
                               'scrapeConfigs': None,
                               'serverFiles': {'prometheus.yml': {'scrape_configs': [
                                   {'job_name': 'acceptance-empty', 'file_sd_configs': [
                                       {'files': ['/etc/config/acceptance-unused.json']}]}]}}},
                'logging': {'elasticsearch': {'persistence': {'storageClass': 'standard', 'size': '4Gi'},
                                               'heap': '512m',
                                               'resources': {'requests': {'cpu': '100m', 'memory': '768Mi'},
                                                             'limits': {'cpu': '2', 'memory': '1536Mi'}}},
                            'kibana': {'resources': {'requests': {'cpu': '100m', 'memory': '512Mi'},
                                                     'limits': {'cpu': '1', 'memory': '1024Mi'}}}}}

    def helm(self, chart, values):
        import yaml
        path = self.work/'lab-values.yaml'; path.write_text(yaml.safe_dump(values))
        rendered = run(['helm', 'template', RELEASE, chart, '-n', NAMESPACE, '-f', path])
        objects = [o for o in yaml.safe_load_all(rendered) if o]
        for obj in objects:
            if obj['kind']=='ConfigMap' and obj['metadata']['name']=='fhs-prometheus':
                cfg = yaml.safe_load(obj['data']['prometheus.yml'])
                require(all(not j.get('static_configs') for j in cfg['scrape_configs']),
                        'Static exporter scrape detected in lab render')
        run(['helm', 'upgrade', '--install', RELEASE, chart, '--kube-context', CONTEXT,
             '-n', NAMESPACE, '-f', path, '--wait', '--wait-for-jobs', '--timeout', '25m'], timeout=1600)
        # Workloads and bounded Jobs must actually converge.
        for obj in self.get('deployments,statefulsets')['items']:
            self.kubectl('rollout', 'status', obj['kind'].lower()+'/'+obj['metadata']['name'], '--timeout=600s')
        for job in self.get('jobs')['items']:
            require(job['status'].get('succeeded', 0)==1, 'Setup Job incomplete '+job['metadata']['name'])
        return [o['metadata']['name'] for o in self.get('jobs')['items']]

    def snapshot(self):
        workloads = self.get('deployments,statefulsets')['items']
        pods = self.get('pods')['items']
        return {'templates': {o['metadata']['name']: digest(o['spec']['template']) for o in workloads},
                'pods': {p['metadata']['name']: p['metadata']['uid'] for p in pods
                         if not any(r['kind']=='Job' for r in p['metadata'].get('ownerReferences', []))},
                'volumes': {p['metadata']['name']: {'uid': p['metadata']['uid'], 'volume': p['spec'].get('volumeName')}
                            for p in self.get('pvc')['items']},
                'credentials_digest': digest(self.get('secret', 'fhs-platform-credentials')['data'])}

    def native(self, base, stage):
        path = self.work/'private-netbox.json'
        path.write_text(json.dumps({'url': base+PREFIX+'/netbox', 'token': self.credentials['api_token']})); path.chmod(0o600)
        reports = {}
        try:
            for script in ('acceptance.py', 'acceptance_fru.py'):
                report = self.work/(stage+'-'+script+'.json')
                if not (stage=='baseline' and report.is_file()):
                    run([sys.executable, ROOT/'ops/platform/inventory-alignment'/script,
                         '--credentials', path, '--report', report], timeout=1800)
                result = json.loads(report.read_text())
                require(result.get('checks_passed', 0)>0, 'Native importer harness did not finish '+script)
                if result.get('device_id'):
                    self.api(base, 'dcim/devices/'+str(result['device_id'])+'/')
                reports[script] = result
        finally:
            path.unlink(missing_ok=True)
        self.record('native_'+stage, reports)

    def ensure_admin_api(self):
        # NetBox 4.7's image only creates a v2 token with an explicit API key.
        # This isolated fixture reuses the chart Secret's legacy token for the
        # existing native importer harness; no inventory/password is changed.
        script = '''import json,sys
from users.models import User,Token
value=json.load(sys.stdin)["token"]
u=User.objects.get(username="admin")
assert u.is_superuser and u.is_active
if not Token.objects.filter(version=1,plaintext=value).exists():
    Token.objects.create(user=u,version=1,token=value,write_enabled=True,description="Isolated native importer acceptance")
print("Isolated importer API credential ready")
'''
        self.kubectl('exec', '-i', 'deployment/fhs-netbox', '--', '/opt/netbox/venv/bin/python',
                     '/opt/netbox/netbox/manage.py', 'shell', '-c', script,
                     obj={'token': self.credentials['api_token']})
        self.evidence['admin_api_bootstrap']={'scope': 'isolated native importer fixture',
                                            'existing_secret_reused': True, 'passwords_unchanged': True}

    def api(self, base, path, data=None, method='GET', token=None, allowed=(200, 201)):
        token = token or self.credentials['api_token']
        return request(base+PREFIX+'/netbox/api/'+path, data, method,
                       {'Authorization': ('Bearer ' if token.startswith('nbt_') else 'Token ')+token}, allowed)

    def inventory(self, base):
        result = {}
        for path in ('plugins/inventory/assets/', 'core/object-changes/', 'extras/journal-entries/'):
            page = path+'?limit=1000'
            rows = []
            while page:
                response = self.api(base, page); rows.extend(response['results'])
                page = response.get('next')
                if page:
                    page = page.split('/api/', 1)[1]
            result[path] = {str(row['id']): digest(stable_api(row)) for row in rows}
        require(result['plugins/inventory/assets/'] and result['core/object-changes/'], 'Baseline inventory/history empty')
        return result

    def provision_discovery_token(self, existing=None):
        # Django ORM is used ONLY to create auth principals/permissions. Inventory access uses REST.
        script = '''from users.models import User
from django.contrib.contenttypes.models import ContentType
from users.models import ObjectPermission, Token
u,_=User.objects.get_or_create(username="fhs-discovery",defaults={"is_active":True})
p,_=ObjectPermission.objects.get_or_create(name="FHS discovery read only",defaults={"actions":["view"],"constraints":{"status":"active"}})
p.actions=["view"]
p.constraints=[{"status":"active","custom_field_data__prometheus_exporters__contains":[v]} for v in ("node","fhs")]
p.save()
p.object_types.set(ContentType.objects.filter(app_label="dcim",model="device"))
p.users.add(u)
import sys,json,secrets
token=json.load(sys.stdin).get("existing") or secrets.token_hex(20)
t=Token.objects.filter(user=u,version=1,plaintext=token).first()
if t is None:
    t=Token.objects.create(user=u,version=1,token=token,write_enabled=False,description="Isolated HTTP discovery acceptance")
assert not t.write_enabled
print(token)
'''
        token = self.kubectl('exec', '-i', 'deployment/fhs-netbox', '--', '/opt/netbox/venv/bin/python',
                            '/opt/netbox/netbox/manage.py', 'shell', '-c', script, obj={'existing':existing}).decode().strip().splitlines()[-1]
        require(len(token)>=40 and ' ' not in token, 'Discovery token generation failed')
        self.apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'fhs-netbox-discovery'},
                    'stringData': {'token': token}})
        return token

    def discovery(self, base, prometheus, token):
        from urllib.parse import urlencode
        def ensure(path, lookup, payload):
            rows=self.api(base,path+'?'+urlencode(lookup))['results']
            require(len(rows)<=1, 'Ambiguous owned discovery fixture '+path)
            if rows:
                return self.api(base,path+str(rows[0]['id'])+'/',payload,'PATCH')
            return self.api(base,path,payload,'POST')
        choices=ensure('extras/custom-field-choice-sets/', {'name':'Prometheus exporters'},
                       {'name':'Prometheus exporters','extra_choices':[['node','Node exporter'],['fhs','FHS exporter']]})
        ensure('extras/custom-fields/', {'name':'prometheus_exporters'},
               {'name':'prometheus_exporters','label':'Prometheus exporters','type':'multiselect',
                'object_types':['dcim.device'],'choice_set':choices['id'],'default':[]})
        path = 'plugins/prometheus-sd/devices/?status=active&cf_prometheus_exporters=node'
        endpoint = base+PREFIX+'/netbox/api/'+path
        request(endpoint, allowed=(401, 403))
        self.api(base, 'dcim/sites/', {'name': 'Forbidden'}, 'POST', token=token, allowed=(403,))
        tags = [ensure('extras/tags/', {'slug': n}, {'name': n, 'slug': n}) for n in ('node-exporter', 'fhs-exporter')]
        manufacturer = ensure('dcim/manufacturers/', {'slug': 'http-discovery-lab'}, {'name': 'HTTP discovery lab', 'slug': 'http-discovery-lab'})
        site = ensure('dcim/sites/', {'slug': 'discovery-lab'}, {'name': 'Discovery lab', 'slug': 'discovery-lab'})
        role = ensure('dcim/device-roles/', {'slug': 'exporter-lab'}, {'name': 'Exporter lab', 'slug': 'exporter-lab'})
        dtype = ensure('dcim/device-types/', {'slug': 'synthetic'}, {'manufacturer': manufacturer['id'], 'model': 'Synthetic', 'slug': 'synthetic'})
        # Real bounded lab exporter process. No host mounts or host networking.
        code = 'from http.server import BaseHTTPRequestHandler,HTTPServer\nimport threading\nclass H(BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200);self.send_header("Content-Type","text/plain; version=0.0.4");self.end_headers();self.wfile.write(b"# TYPE fhs_acceptance gauge\\nfhs_acceptance 1\\n")\n def log_message(self,*a):pass\nfor p in (9100,9110):threading.Thread(target=HTTPServer(("0.0.0.0",p),H).serve_forever,daemon=True).start()\nthreading.Event().wait()'
        existing=next((p for p in self.get('pods')['items'] if p['metadata']['name']=='synthetic-exporter'),None)
        if existing and existing['spec']['containers'][0]['command']!=['python','-c',code]:
            self.kubectl('delete','pod/synthetic-exporter','--wait=true','--timeout=60s')
        self.apply({'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': 'synthetic-exporter', 'labels': {'fhs-acceptance-owner': OWNER}},
                    'spec': {'automountServiceAccountToken': False, 'containers': [{'name': 'exporter',
                    'image': 'python:3.12-alpine', 'command': ['python', '-c', code],
                    'resources': {'requests': {'cpu': '10m', 'memory': '24Mi'}, 'limits': {'cpu': '100m', 'memory': '64Mi'}}}]}})
        self.kubectl('wait', '--for=condition=Ready', 'pod/synthetic-exporter', '--timeout=180s')
        ip = self.get('pod', 'synthetic-exporter')['status']['podIP']
        common = {'device_type': dtype['id'], 'role': role['id'], 'site': site['id'], 'status': 'active'}
        old=self.api(base,'dcim/devices/?name=discovery-renamed')['results']
        if old:
            require(len(old)==1, 'Ambiguous renamed discovery fixture')
            self.api(base,'dcim/devices/'+str(old[0]['id'])+'/',{'name':'discovery-selected'},'PATCH')
        device = ensure('dcim/devices/', {'name': 'discovery-selected'}, dict(common, name='discovery-selected', tags=[], custom_fields={'prometheus_exporters':['node','fhs']}))
        interface = ensure('dcim/interfaces/', {'device_id': device['id'], 'name': 'eth0'}, {'device': device['id'], 'name': 'eth0', 'type': 'other'})
        address = ensure('ipam/ip-addresses/', {'address': ip+'/32'}, {'address': ip+'/32', 'assigned_object_type': 'dcim.interface',
                           'assigned_object_id': interface['id']})
        self.api(base, 'dcim/devices/'+str(device['id'])+'/', {'primary_ip4': address['id']}, 'PATCH')
        other = ensure('dcim/devices/', {'name': 'discovery-unselected'}, dict(common, name='discovery-unselected', tags=[t['id'] for t in tags], custom_fields={'prometheus_exporters':[]}))
        sd = self.api(base, path, token=token)
        require('discovery-selected' in json.dumps(sd) and 'discovery-unselected' not in json.dumps(sd), 'Actual discovery selection failed')
        def targets():
            return request(prometheus+'/api/v1/targets')['data']['activeTargets']
        def selected(name):
            return [t for t in targets() if t.get('labels', {}).get('node_name')==name]
        def healthy():
            rows = selected('discovery-selected')
            return rows if len(rows)==2 and all(t['health']=='up' for t in rows) else False
        rows = wait_for(healthy, 'Prometheus adds both running exporters', 180)
        for row in rows:
            labels = row['labels']
            require(labels.get('site')=='discovery-lab' and labels.get('role')=='exporter-lab' and
                    labels.get('device')=='discovery-selected', 'Discovery labels wrong')
            require(row['scrapeUrl'].startswith('http://'+ip+':'), 'Scrape escaped synthetic exporter')
        self.api(base, 'dcim/devices/'+str(device['id'])+'/', {'custom_fields':{'prometheus_exporters':['node']}}, 'PATCH')
        wait_for(lambda: len(selected('discovery-selected'))==1 and selected('discovery-selected')[0]['labels']['job']=='node', 'Independent exporter deselection', 120)
        self.api(base, 'dcim/devices/'+str(device['id'])+'/', {'custom_fields':{'prometheus_exporters':['node','fhs']}}, 'PATCH')
        wait_for(healthy, 'Both exporters reselected', 120)
        self.api(base, 'dcim/devices/'+str(device['id'])+'/', {'name': 'discovery-renamed'}, 'PATCH')
        wait_for(lambda: len(selected('discovery-renamed'))==2 and not selected('discovery-selected'), 'Discovery update', 120)
        self.api(base, 'dcim/devices/'+str(device['id'])+'/', {'status': 'offline'}, 'PATCH')
        wait_for(lambda: not selected('discovery-renamed'), 'Inactive removal', 120)
        self.api(base, 'dcim/devices/'+str(device['id'])+'/', {'status': 'active', 'custom_fields':{'prometheus_exporters':[]}}, 'PATCH')
        time.sleep(12)
        require(not selected('discovery-renamed'), 'Device with no selected exporters was selected')
        self.api(base, 'dcim/devices/'+str(device['id'])+'/', {'custom_fields':{'prometheus_exporters':['node','fhs']}}, 'PATCH')
        wait_for(lambda: len(selected('discovery-renamed'))==2, 'Reselection', 120)
        self.api(base, 'dcim/devices/'+str(device['id'])+'/', method='DELETE', allowed=(204,))
        wait_for(lambda: not selected('discovery-renamed'), 'Deleted device removal', 120)
        self.record('discovery', {'authenticated': True, 'read_only': True, 'active_custom_field_filter': True,
                    'jobs': sorted(t['labels']['job'] for t in rows), 'targets': [t['scrapeUrl'] for t in rows],
                    'update_inactive_clear_delete_refresh': True, 'helm_changes_during_refresh': 0, 'independent_exporter_selection':True})

    def routes(self):
        import re
        results = {}
        ingress = run(['minikube', '-p', CONTEXT, 'ip']).decode().strip()
        for suffix in ('', 'netbox/', 'grafana/', 'mid-cbf-kibana/'):
            html = request('http://'+ingress+PREFIX+'/'+suffix, headers={'Host': 'localhost'})
            require(isinstance(html, str), 'Ingress route did not return HTML '+suffix)
        results['ingress'] = {'host': 'localhost', 'prefix': PREFIX, 'routes_checked': 4}
        with self.forward(RELEASE+'-hw-landing', 8080) as landing:
            html = request(landing+PREFIX+'/')
            for path in ('netbox', 'grafana', 'mid-cbf-kibana'):
                require('href="'+PREFIX+'/'+path+'/"' in html, 'Landing app link missing')
            require('http://' not in html and 'https://' not in html, 'Landing external asset')
            results['landing'] = {'links': 3, 'local_inline_assets': True}
        for service, port, path in [('fhs-netbox',80,'netbox'), ('fhs-grafana',80,'grafana'),
                                    (RELEASE+'-elastic-kibana',5601,'mid-cbf-kibana')]:
            with self.forward(service, port) as base:
                html = request(base+PREFIX+'/'+path+'/', allowed=(200,))
                require(isinstance(html, str), 'App route did not return HTML '+path)
                assets = re.findall(r'(?:src|href)=["\']([^"\']+\.(?:css|js)(?:\?[^"\']*)?)["\']', html)
                require(assets, 'No actual assets found '+path)
                from urllib.parse import urljoin, urlsplit
                document=base+PREFIX+'/'+path+'/'
                base_tag=re.search(r'<base[^>]+href=["\']([^"\']+)',html)
                asset_base=urljoin(document,base_tag.group(1)) if base_tag else document
                resolved=[urljoin(asset_base,a) for a in assets]
                asset=next((a for a in resolved if urlsplit(a).netloc==urlsplit(base).netloc
                            and urlsplit(a).path.startswith(PREFIX+'/'+path+'/')),None)
                require(asset, 'App assets do not honor prefix '+path)
                request(asset)
                results[path] = {'route': PREFIX+'/'+path+'/', 'asset_fetched': urlsplit(asset).path}
        self.record('routes', results)

    def elastic(self, base, path, data=None, method='GET', writer=False, allowed=(200, 201)):
        user = 'filebeat_writer' if writer else 'elastic'
        password = self.credentials['filebeat-password' if writer else 'elastic-password']
        auth = base64.b64encode((user+':'+password).encode()).decode()
        return request(base+'/'+path.lstrip('/'), data, method, {'Authorization': 'Basic '+auth, 'kbn-xsrf': 'acceptance'}, allowed)

    def logging_assets(self, es, kibana):
        template = self.elastic(es, '_index_template/filebeat-9.5.5')
        policy = self.elastic(es, '_ilm/policy/filebeat')
        pipelines = self.elastic(es, '_ingest/pipeline/filebeat-9.5.5-system-*')
        require(len(template['index_templates'])==1, 'Exact versioned Filebeat template missing')
        require(policy['filebeat']['policy']['phases']['delete']['min_age']=='30d', 'Retention policy missing')
        require(any('syslog' in p for p in pipelines) and any('auth' in p for p in pipelines), 'System pipelines missing')
        view = self.elastic(kibana, PREFIX+'/mid-cbf-kibana/api/data_views/data_view/fhs-filebeat')
        require(view['data_view']['title']=='filebeat-*' and view['data_view']['timeFieldName']=='@timestamp', 'Data view wrong')
        # Exclude transient ES metadata (version/modified date); compare owned definitions.
        return {'template': template, 'policy': policy['filebeat']['policy'], 'pipelines': pipelines,
                'data_view': view['data_view']}

    def logging(self, es, kibana):
        jobs = self.get('jobs')['items']
        setup = [j for j in jobs if '-filebeat-setup-' in j['metadata']['name']]
        require(setup and all(j['status'].get('succeeded')==1 for j in setup), 'Filebeat setup did not complete')
        for obj in self.get('deployments,statefulsets,daemonsets')['items']:
            require('beats/filebeat' not in json.dumps(obj), 'Persistent Filebeat collector detected')
        for pod in self.get('pods')['items']:
            require(not any('hostPath' in v for v in pod['spec'].get('volumes', [])), 'Host mount in acceptance namespace')
        assets = self.logging_assets(es, kibana)
        # Exercise the exact default versioned destination used by roles/filebeat; a finite event only.
        event_id = 'acceptance-'+uuid.uuid4().hex
        event = {'@timestamp': datetime.now(timezone.utc).isoformat(), 'message': 'Bounded acceptance event',
                 'agent': {'type': 'filebeat', 'version': '9.5.5'}, 'log': {'level': 'info'}}
        self.elastic(es, 'filebeat-9.5.5/_create/'+event_id+'?refresh=true', event, 'PUT', writer=True)
        self.elastic(es, 'unauthorized-acceptance/_doc/'+event_id, event, 'PUT', writer=True, allowed=(403,))
        self.elastic(es, '_security/role/acceptance-forbidden', {'cluster': ['all']}, 'PUT', writer=True, allowed=(403,))
        stored = self.elastic(es, 'filebeat-9.5.5/_search', {'query': {'ids': {'values': [event_id]}}}, 'POST')
        require(stored['hits']['total']['value']==1 and stored['hits']['hits'][0]['_source']==event, 'Limited publisher event missing')
        self.record('logging', {'completed_setup_jobs': [j['metadata']['name'] for j in setup],
                    'template': 'filebeat-9.5.5', 'policy': 'filebeat', 'pipeline_ids': sorted(assets['pipelines']),
                    'data_view': 'fhs-filebeat', 'limited_writer_ingested': True, 'unauthorized_write_denied': True,
                    'event_id': event_id, 'persistent_collectors': 0})
        return assets, event_id, event

    def execute(self, resume=False):
        native_final_cache=None
        if resume:
            previous = json.loads(self.path.read_text())
            require(previous.get('context')==CONTEXT and previous.get('namespace')==NAMESPACE,
                    'Resume report scope does not match')
            require(previous.get('status')=='failed' and 'baseline' in previous.get('checks', {}),
                    'Resume requires a failed run with a completed baseline')
            old_work = Path(previous['evidence_directory'])
            require(str(old_work).startswith('/tmp/fhs-discovery-acceptance-') and old_work.is_dir(),
                    'Missing retained acceptance evidence')
            self.work.rmdir(); self.work=old_work
            (self.work/('attempt-'+uuid.uuid4().hex+'.json')).write_text(json.dumps(previous, indent=2)+'\n')
            current_sources=json.loads((ROOT/'candidate.json').read_text())
            prefixes=('platform/charts/fhs-platform/','playbooks/netbox/','ops/platform/inventory-alignment/')
            def native_sources(hashes):
                return {k:v for k,v in hashes.items() if k.startswith(prefixes)}
            if (previous.get('checks',{}).get('native_final') and
                    native_sources(previous['candidate_sha256'])==native_sources(current_sources)):
                native_final_cache=(previous['checks']['native_final'],previous['checks']['upgrade']['snapshot'])
            self.evidence=previous
            self.evidence.pop('failure', None)
            self.evidence['checks']={k:v for k,v in previous['checks'].items()
                                     if k in ('preflight','baseline','native_baseline')}
            self.evidence.setdefault('resumed_at', []).append(datetime.now(timezone.utc).isoformat())
            ns=self.get('namespace', NAMESPACE, namespace=False)
            require(ns['metadata']['labels'].get('fhs-acceptance-owner')==OWNER, 'Resume namespace not owned')
            require(all(any(c['type']=='Ready' and c['status']=='True' for c in n['status']['conditions'])
                        for n in self.get('nodes', namespace=False)['items']), 'Resume nodes not Ready')
            self.evidence['candidate_sha256']=json.loads((ROOT/'candidate.json').read_text())
        else:
            self.preflight()
        values = self.values()
        if not resume:
            jobs = self.helm(self.baseline_chart, values)
        secret = self.get('secret', 'fhs-platform-credentials')['data']
        self.credentials = {k: base64.b64decode(v).decode() for k,v in secret.items()}
        self.ensure_admin_api()
        if resume:
            before=self.evidence['checks']['baseline']['snapshot']
            now=self.snapshot()
            require(before['volumes']==now['volumes'] and before['credentials_digest']==now['credentials_digest'],
                    'Retained baseline PVCs or credentials changed')
        else:
            before = self.snapshot()
            self.record('baseline', {'jobs': jobs, 'snapshot': before, 'fresh_install': True})
        with self.forward('fhs-netbox', 80) as netbox:
            if 'native_baseline' not in self.evidence['checks']:
                self.native(netbox, 'baseline')
            inventory = self.evidence.get('baseline_inventory') or self.inventory(netbox)
            current=self.inventory(netbox)
            require(all(current[p].get(key)==value for p,rows in inventory.items() for key,value in rows.items()),
                    'Retained baseline inventory changed before upgrade')
            self.evidence['baseline_inventory']=inventory; self.save()
        secrets_by_name={s['metadata']['name']:s for s in self.get('secrets')['items']}
        if 'fhs-netbox-discovery' in secrets_by_name:
            token=base64.b64decode(secrets_by_name['fhs-netbox-discovery']['data']['token']).decode()
        else:
            token = None
        token=self.provision_discovery_token(token)
        values['global']['discovery']['enabled'] = True
        jobs = self.helm(ROOT/'platform/charts/fhs-platform', values)
        after = self.snapshot()
        self.record('upgrade', {'jobs': jobs, 'same_release': RELEASE, 'snapshot': after})
        expected = {'fhs-netbox', 'fhs-netbox-worker', 'fhs-prometheus'}
        changed = {name for name in before['templates'] if before['templates'][name]!=after['templates'].get(name)}
        require(changed<=expected, 'Unrelated workload template changed: '+str(changed-expected))
        unchanged = set(before['templates'])-expected
        require(len(unchanged)>=6, 'Incomplete unrelated workload coverage')
        require(before['volumes']==after['volumes'], 'PVC identity or binding changed')
        require(before['credentials_digest']==after['credentials_digest'], 'Credentials changed')
        # Map stable pod owners through ReplicaSets, rather than trusting names.
        for name, uid in before['pods'].items():
            if not any(name==w or name.startswith(w+'-') for w in expected):
                require(after['pods'].get(name)==uid, 'Unrelated pod UID changed '+name)
        with self.forward('fhs-netbox', 80) as netbox:
            preserved = self.inventory(netbox)
            for path, rows in inventory.items():
                require(all(preserved[path].get(key)==value for key,value in rows.items()), 'Inventory/history changed '+path)
            self.record('inventory_preserved', {'counts': {p: len(v) for p,v in inventory.items()}, 'all_ids_and_payloads_equal': True})
            if native_final_cache:
                cached, prior=native_final_cache
                consumers=('fhs-netbox','fhs-netbox-worker')
                require(all(prior['templates'][n]==after['templates'][n] for n in consumers),
                        'Cached native consumer templates changed')
                require({n:u for n,u in prior['pods'].items() if any(n.startswith(c+'-') for c in consumers)}==
                        {n:u for n,u in after['pods'].items() if any(n.startswith(c+'-') for c in consumers)},
                        'Cached native consumer pods changed')
                self.evidence['native_final_reused']={'unchanged_chart_and_importer_hashes':True,
                                                      'unchanged_netbox_pod_uids':True}
                self.record('native_final',cached)
            else:
                self.native(netbox, 'final')
            with self.forward('fhs-prometheus', 9090) as prometheus:
                self.discovery(netbox, prometheus, token)
        self.routes()
        with self.forward(RELEASE+'-elastic', 9200) as es, self.forward(RELEASE+'-elastic-kibana', 5601) as kibana:
            assets, event_id, event = self.logging(es, kibana)
            # Custom saved object and policy prove reapplication preserves operator ownership.
            self.elastic(es, '_ilm/policy/acceptance-custom', {'policy': {'phases': {}}}, 'PUT')
            custom_url = PREFIX+'/mid-cbf-kibana/api/saved_objects/dashboard/acceptance-custom'
            self.elastic(kibana, custom_url, {'attributes': {'title': 'Acceptance custom dashboard'}}, 'POST', allowed=(200, 201, 409))
            require(self.elastic(kibana, custom_url)['attributes']['title']=='Acceptance custom dashboard',
                    'Existing acceptance dashboard was replaced')
            registry_before = self.elastic(kibana, PREFIX+'/mid-cbf-kibana/api/data_views')['data_view']
            stable = self.snapshot()
            jobs = self.helm(ROOT/'platform/charts/fhs-platform', values)
            final = self.snapshot()
            require(stable==final, 'Idempotent upgrade changed workload/pods/PVCs/credentials')
            require(self.logging_assets(es, kibana)==assets, 'Setup reapply changed owned definitions')
            stored = self.elastic(es, 'filebeat-9.5.5/_search', {'query': {'ids': {'values': [event_id]}}}, 'POST')
            require(stored['hits']['total']['value']==1 and stored['hits']['hits'][0]['_source']==event, 'Setup reapply lost or duplicated document')
            self.elastic(es, '_ilm/policy/acceptance-custom')
            self.elastic(kibana, custom_url)
            require(self.elastic(kibana, PREFIX+'/mid-cbf-kibana/api/data_views')['data_view']==registry_before,
                    'Duplicate or changed data view registry')
            self.record('idempotence', {'jobs': jobs, 'document_preserved': True, 'custom_objects_preserved': True,
                                       'registry_preserved': True, 'definitions_preserved': True})
        self.record('preservation', {'unchanged_workloads': sorted(unchanged), 'changed_workloads': sorted(changed),
                    'pvc_bindings_and_uids_preserved': True, 'credentials_preserved': True,
                    'unrelated_pod_uids_preserved': True, 'idempotent_upgrade_all_pods_preserved': True})
        require(REQUIRED==set(self.evidence['checks']), 'Missing required coverage')
        self.evidence['status'] = 'passed'

    def finish(self):
        for proc in self.forwards:
            proc.terminate(); proc.wait(timeout=10)
        self.credentials.clear()
        (self.work/'private-netbox.json').unlink(missing_ok=True)
        self.evidence['finished_at'] = datetime.now(timezone.utc).isoformat()
        self.save()


def bundle(destination):
    """Allowlisted source transfer; never include private values, .git, or controller runs."""
    evidence = json.loads((ROOT/'ops/platform/discovery-portal-setup/source-evidence.json').read_text())
    with tarfile.open(destination, 'w:gz') as tar:
        hashes = {}
        for path in ('platform/charts/fhs-platform', 'playbooks/netbox', 'ops/platform/inventory-alignment',
                     'ops/platform/discovery-portal-setup'):
            for file in sorted((ROOT/path).rglob('*')):
                if file.is_file() and '__pycache__' not in file.parts and file.suffix not in ('.pyc',):
                    # Chart values are public committed defaults plus this candidate's intended changes.
                    require(file.name!='site-values.yaml', 'Private site values in transfer allowlist')
                    relative = str(file.relative_to(ROOT))
                    hashes[relative] = hashlib.sha256(file.read_bytes()).hexdigest()
                    tar.add(file, arcname=relative, recursive=False)
        for entry in evidence['archives']:
            data = run(['git', 'archive', '--format=tar', entry['revision'], 'platform/charts/fhs-platform'])
            require(hashlib.sha256(data).hexdigest()==entry['sha256'], 'Baseline digest mismatch')
            info = tarfile.TarInfo('baselines/'+entry['archive']); info.size=len(data)
            tar.addfile(info, io.BytesIO(data))
        data = json.dumps(hashes, sort_keys=True).encode()
        info = tarfile.TarInfo('candidate.json'); info.size=len(data); tar.addfile(info, io.BytesIO(data))


def orchestrate(args):
    ssh = ['ssh', '-F', '/home/dragonlord/.ssh/config', '-o', 'ConnectTimeout=5', 'dragonvm']
    # Read-only reachability check; wake recovery belongs to the local orchestration authority.
    run(ssh+['true'], timeout=15)
    with tempfile.TemporaryDirectory(prefix='fhs-discovery-transfer-') as folder:
        archive = Path(folder)/'candidate.tgz'; bundle(archive)
        remote = run(ssh+['mktemp -d /tmp/fhs-discovery-supervised.XXXXXXXX'], timeout=15).decode().strip()
        require(remote.startswith('/tmp/fhs-discovery-supervised.') and '\n' not in remote, 'Invalid remote path')
        run(ssh+['tar -xzf - -C '+shlex.quote(remote)], data=archive.read_bytes(), timeout=120)
        # Existing isolated Ansible environments may be selected without installing host agents.
        command = ('cd '+shlex.quote(remote)+' && '
                   'export PATH=/home/dragon-lord/.local/bin:$PATH; '
                   'export ANSIBLE_COLLECTIONS_PATH=/tmp/fhs-discovery-collections; '
                   'for p in /tmp/fhs-discovery-tools-venv/bin /tmp/fhs-molecule-venv/bin /tmp/fhs-netbox-venv/bin /tmp/fhs-ansible-venv/bin /tmp/fhs-inventory-venv/bin; do '
                   'if [ -x "$p/ansible" ]; then export PATH="$p:$PATH"; break; fi; done; '
                   'python3 ops/platform/discovery-portal-setup/acceptance.py --on-dragonvm '
                   '--context fhs-test --namespace fhs-discovery-portal-test --report '+shlex.quote(remote+'/report.json'))
        result = subprocess.run(ssh+[command], capture_output=True, timeout=7200)
        report = run(ssh+['cat '+shlex.quote(remote+'/report.json')], timeout=30)
        Path(args.report).write_bytes(report)
        require(result.returncode==0 and json.loads(report)['status']=='passed',
                'Live acceptance failed; sanitized report: '+args.report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--namespace', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--on-dragonvm', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--resume', action='store_true', help='Resume retained failed-run evidence after fixing its cause')
    args = parser.parse_args()
    validate_scope(args.context, args.namespace)
    if not args.on_dragonvm and (Path.home()/'.minikube/profiles/fhs-test').is_dir():
        # The controller may run on dragonvm itself; preserve the same source
        # snapshot/baseline validation without trying to SSH back to this host.
        with tempfile.TemporaryDirectory(prefix='fhs-discovery-supervised-') as folder:
            root = Path(folder); archive = root/'candidate.tgz'; bundle(archive)
            with tarfile.open(archive) as tar:
                tar.extractall(root, filter='data')
            return subprocess.run([sys.executable, str(root/'ops/platform/discovery-portal-setup/acceptance.py'),
                                   '--on-dragonvm', '--context', args.context, '--namespace', args.namespace,
                                   '--report', str(Path(args.report).resolve())]+(['--resume'] if args.resume else []), env=os.environ).returncode
    if args.on_dragonvm:
        acceptance = Acceptance(args.report)
        try:
            acceptance.execute(resume=args.resume)
        except Exception as error:
            message = str(error)
            for secret in acceptance.credentials.values():
                if secret:
                    message = message.replace(secret, '<redacted>')
            acceptance.evidence['failure'] = {'type': type(error).__name__,
                'after_checks': list(acceptance.evidence['checks']), 'message': message[:1000]}
            raise SystemExit(1) from None
        finally:
            acceptance.finish()
    else:
        try:
            orchestrate(args)
        except Exception as error:
            if not Path(args.report).exists():
                Path(args.report).write_text(json.dumps({'status': 'failed', 'failure': type(error).__name__,
                    'checks': {}, 'limitations': ['Remote preflight or source transfer failed; no runtime success claimed.']})+'\n')
            print('FAIL: supervised acceptance; see '+args.report, file=sys.stderr)
            return 1
    return 0


if __name__=='__main__':
    sys.exit(main())
