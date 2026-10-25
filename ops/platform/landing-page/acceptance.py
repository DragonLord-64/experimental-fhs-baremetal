#!/usr/bin/env python3
"""Controller-only bounded acceptance of the delivered chart on the retained lab."""
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import tarfile
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('lab', ROOT/'ops/platform/discovery-portal-setup/acceptance.py')
lab = importlib.util.module_from_spec(spec); spec.loader.exec_module(lab)
FIXTURE = 'fhs-landing-acceptance'


def local(args):
    started = time.monotonic()
    report = {'status':'failed', 'checks':{}, 'limitations':[
        'HTTP lab ingress; no TLS or physical hardware test.',
        'Native NetBox acceptance reused from the preceding passed recovery and full integration; importer/plugin sources unchanged.']}
    class Bounded(lab.Acceptance):
        def kubectl(self, *parts, obj=None, namespace=True):
            return lab.run(self.k+(['-n', lab.NAMESPACE] if namespace else [])+list(parts),
                           data=json.dumps(obj).encode() if obj is not None else None,
                           timeout=650 if parts[0]=='rollout' else 90)
    check = Bounded(args.report)
    os.environ.setdefault('FHS_ACCEPTANCE_DIAGNOSTICS', str(check.work/'diagnostics'))
    report['diagnostics_directory'] = os.environ['FHS_ACCEPTANCE_DIAGNOSTICS']
    scales, crons, created = [], [], []
    upgraded = False
    stage = 'inspect owned release, services and capacity'
    values = Path('/tmp/fhs-discovery-acceptance-7fe5ixpb/lab-values.yaml')
    renderer = check.work/'render.py'
    fixture_values = check.work/'landing-values.json'
    fixture_values.write_text(json.dumps({'landing':{
        'introduction':'# Installation operations\n**Daily checks** and [documentation](https://docs.example.invalid/).\n<script>unsafe</script>',
        'links':[{'name':'Jira','url':'https://jira.example.invalid/'},
                 {'name':'Repository','url':'https://github.com/DragonLord-64/experimental-fhs-baremetal'}],
        'extraChecks':[{'id':'acceptance','name':'Acceptance endpoint','url':'/fixture/',
                        'endpoint':'http://'+FIXTURE+':8080/', 'expected':[200]}]}}))
    def retained():
        return {kind:{o['metadata']['name']:(o['metadata']['uid'],
                lab.digest(o.get('data',{})) if kind=='secrets' else o['spec'].get('volumeName'))
                for o in check.get(kind)['items'] if kind!='secrets' or o.get('type')!='helm.sh/release.v1'}
                for kind in ('pvc','secrets')}
    def make_renderer(active):
        desired = {n:(max(1,c) if active and n in required else c) for _,n,c in scales}
        renderer.write_text('''#!/usr/bin/env python3
import sys,yaml
scales = '''+repr(desired)+'''
for obj in yaml.safe_load_all(sys.stdin):
    if not obj or obj['kind']=='Job': continue
    if obj['kind'] in ('Deployment','StatefulSet'):
        obj['spec']['replicas']=scales.get(obj['metadata']['name'],1)
    if obj['kind']=='CronJob': obj['spec']['suspend']=True
    print(yaml.safe_dump(obj),end='---\\n')
''')
        renderer.chmod(0o700)
    def upgrade(prefix=None, fixtures=True):
        command = ['helm','upgrade',lab.RELEASE,ROOT/'platform/charts/fhs-platform',
                   '--kube-context',lab.CONTEXT,'-n',lab.NAMESPACE,'-f',values,
                   '--post-renderer',renderer,'--timeout','10m']
        if fixtures: command += ['-f',fixture_values]
        if prefix is not None: command += ['--set-string','global.urlPrefix='+prefix]
        lab.run(command,timeout=650)
        check.kubectl('rollout','status','deployment/'+lab.RELEASE+'-hw-landing','--timeout=180s')
    def ingress_get(path):
        with urlopen(Request(origin+path, headers={'Host':host}),timeout=15) as response:
            lab.require(response.status==200,'Ingress response')
            return response.read(), response.headers
    def statuses(prefix):
        return json.loads(ingress_get(prefix+'/status.json')[0])
    def deadline(*unused):
        raise TimeoutError('Acceptance deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(2400)
    try:
        lab.require(values.is_file(),'Retained private values missing')
        ns = check.get('namespace',lab.NAMESPACE,namespace=False)
        lab.require(ns['metadata'].get('labels',{}).get('fhs-acceptance-owner')==lab.OWNER,'Namespace ownership')
        release = json.loads(lab.run(['helm','list','--kube-context',lab.CONTEXT,'-n',lab.NAMESPACE,'-o','json']))
        lab.require(any(o['name']==lab.RELEASE for o in release),'Owned release missing')
        report['checks']['services_inspected'] = len(check.get('services',namespace=False)['items'])
        nodes = check.get('nodes',namespace=False)['items']
        report['checks']['capacity'] = [{'cpu':n['status']['allocatable']['cpu'],
                                         'memory':n['status']['allocatable']['memory']} for n in nodes]
        workloads = check.get('deployments,statefulsets')['items']
        scales = [(o['kind'].lower(),o['metadata']['name'],o['spec'].get('replicas',1)) for o in workloads]
        report['checks']['original_scales'] = {n:c for _,n,c in scales}
        crons = [(o['metadata']['name'],o['spec'].get('suspend',False)) for o in check.get('cronjobs')['items']]
        before = retained()
        required = {'fhs-netbox','fhs-netbox-worker','fhs-postgresql','fhs-valkey-primary',
                    'fhs-grafana',lab.RELEASE+'-elastic',lab.RELEASE+'-elastic-kibana',lab.RELEASE+'-hw-landing'}
        lab.require(required <= {n for _,n,_ in scales},'Expected retained workloads missing')
        ingress = check.get('ingress',lab.RELEASE+'-web')
        host = ingress['spec']['rules'][0]['host']
        prefix = next(p['path'].rstrip('/') for p in ingress['spec']['rules'][0]['http']['paths']
                      if p['backend']['service']['name']==lab.RELEASE+'-hw-landing')
        # Preserve configured ingress controller, hostname and scheme; lab uses HTTP.
        lab.require(not ingress['spec'].get('tls'),'This HTTP-only harness requires the retained HTTP lab')
        origin = 'http://'+lab.run(['minikube','-p',lab.CONTEXT,'ip']).decode().strip()
        for kind in ('deployment','service','configmap'):
            lab.require(not check.get(kind)['items'] or all(o['metadata']['name']!=FIXTURE for o in check.get(kind)['items']),
                        'Fixture name already exists')
        image = 'docker.io/library/python:3.13.7-alpine'
        labels = {'app':FIXTURE,'fhs-acceptance-owner':lab.OWNER}
        code = 'from http.server import HTTPServer,BaseHTTPRequestHandler\nclass H(BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200);self.end_headers()\n def log_message(self,*args):pass\nHTTPServer(("0.0.0.0",8080),H).serve_forever()'
        fixtures = [
            {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':FIXTURE,'labels':labels},'data':{'server.py':code}},
            {'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':FIXTURE,'labels':labels},
             'spec':{'replicas':1,'selector':{'matchLabels':{'app':FIXTURE}},'template':{
                 'metadata':{'labels':labels},'spec':{'automountServiceAccountToken':False,
                 'containers':[{'name':'web','image':image,'command':['python','/app/server.py'],
                     'resources':{'requests':{'cpu':'5m','memory':'16Mi'},'limits':{'cpu':'100m','memory':'64Mi'}},
                     'volumeMounts':[{'name':'code','mountPath':'/app'}]}],
                 'volumes':[{'name':'code','configMap':{'name':FIXTURE}}]}}}},
            {'apiVersion':'v1','kind':'Service','metadata':{'name':FIXTURE,'labels':labels},
             'spec':{'selector':{'app':FIXTURE},'ports':[{'port':8080,'targetPort':8080}]}}]
        for obj in fixtures:
            check.apply(obj); created.append(obj['kind'].lower())
        check.kubectl('rollout','status','deployment/'+FIXTURE,'--timeout=180s')
        make_renderer(True)
        stage = 'upgrade delivered full chart and wait for managed applications'
        upgraded = True
        upgrade()
        for kind,name,_ in scales:
            if name in required:
                check.kubectl('rollout','status',kind+'/'+name,'--timeout=600s')
        stage = 'verify page, links and local assets through shared ingress'
        def page_checks(p):
            body, headers = ingress_get(p+'/')
            text = body.decode()
            for marker in ('<h1>Installation operations</h1>','<strong>Daily checks</strong>',
                           '&lt;script&gt;unsafe&lt;/script&gt;','https://jira.example.invalid/',
                           'href="'+p+'/netbox/"','href="'+p+'/grafana/"','href="'+p+'/mid-cbf-kibana/"'):
                lab.require(marker in text,'Page content/link missing')
            js, js_headers = ingress_get(p+'/landing.js')
            lab.require(b'status.json' in js and 'javascript' in js_headers['Content-Type'],'Self-hosted script')
            lab.require("script-src 'self'" in headers['Content-Security-Policy'],'CSP missing')
            (check.work/('root.html' if not p else 'prefixed.html')).write_bytes(body)
            return {'page':True,'local_script':True,'markdown_and_custom_links':True}
        report['checks']['subpath_ingress'] = lab.wait_for(lambda: page_checks(prefix), 'Initial ingress convergence', 45)
        def reachable():
            result = statuses(prefix)
            return result if all(v['status']=='reachable' for v in result.values()) else None
        initial = lab.wait_for(reachable,'Reachability',240)
        # Visitor traffic must not trigger checks or change their timestamps.
        for _ in range(10): ingress_get(prefix+'/')
        following = statuses(prefix)
        lab.require(all(v['checked'] for v in initial.values()),'Check timestamps missing')
        # May straddle one scheduled cycle: compare elapsed time, rather than assuming no boundary.
        from datetime import datetime
        for key in initial:
            delta = (datetime.fromisoformat(following[key]['checked'])-datetime.fromisoformat(initial[key]['checked'])).total_seconds()
            lab.require(delta==0 or delta>=55,'Visitor-triggered polling')
        report['checks']['cached_status'] = following
        stage = 'controlled owned endpoint failure and recovery'
        check.kubectl('scale','deployment/'+FIXTURE,'--replicas=0')
        lab.wait_for(lambda: statuses(prefix)['acceptance']['status']=='unavailable','Failure cycle',150)
        check.kubectl('scale','deployment/'+FIXTURE,'--replicas=1')
        check.kubectl('rollout','status','deployment/'+FIXTURE,'--timeout=90s')
        lab.wait_for(lambda: statuses(prefix)['acceptance']['status']=='reachable','Recovery cycle',150)
        report['checks']['synthetic_failure_recovery'] = True
        stage = 'root routing through same shared ingress'
        upgrade(prefix='')
        report['checks']['root_ingress'] = lab.wait_for(lambda: page_checks(''), 'Root ingress convergence', 45)
        stage = 'restore prefix and verify again'
        upgrade()
        report['checks']['restored_subpath_ingress'] = lab.wait_for(lambda: page_checks(prefix), 'Restored ingress convergence', 45)
        lab.require(retained()==before,'PVC or credential identity changed')
        report['checks']['pvcs_credentials_preserved'] = True
        report['checks']['rendered_html_directory'] = str(check.work)
        report['limitations'].append('HTML and asset responses retained; no automated browser screenshot.')
        report['status'] = 'passed'
    except Exception as error:
        report['failure'] = {'type':type(error).__name__,'stage':stage}
        if hasattr(error, 'code'):
            report['failure']['http_status'] = error.code
        try:
            report['pod_diagnostics'] = [{'name':p['metadata']['name'],
                'phase':p.get('status',{}).get('phase'),
                'containers':[{'name':c['name'],'restarts':c.get('restartCount',0),
                    'waiting_reason':c.get('state',{}).get('waiting',{}).get('reason')}
                    for c in p.get('status',{}).get('containerStatuses',[])]}
                for p in check.get('pods')['items']]
        except Exception:
            pass
    finally:
        signal.alarm(0)
        cleanup_failures = []
        def cleanup(label, action):
            try:
                action()
            except Exception:
                cleanup_failures.append(label)
        if upgraded:
            def restore_configuration():
                make_renderer(False)
                lab.run(['helm','upgrade',lab.RELEASE,ROOT/'platform/charts/fhs-platform',
                         '--kube-context',lab.CONTEXT,'-n',lab.NAMESPACE,'-f',values,
                         '--post-renderer',renderer,'--timeout','10m'],timeout=650)
            cleanup('configuration', restore_configuration)
        for kind in reversed(created):
            cleanup('fixture '+kind, lambda kind=kind: check.kubectl(
                'delete',kind,FIXTURE,'--wait=true','--timeout=60s'))
        for name,suspended in crons:
            cleanup('cronjob '+name, lambda name=name,suspended=suspended: check.kubectl(
                'patch','cronjob',name,'--type=merge','-p',json.dumps({'spec':{'suspend':suspended}})))
        for kind,name,count in scales:
            cleanup('scale '+name, lambda kind=kind,name=name,count=count: check.kubectl(
                'scale',kind+'/'+name,'--replicas='+str(count)))
        cleanup('scale verification', lambda: lab.require(all(
            check.get(kind,name)['spec'].get('replicas',1)==count for kind,name,count in scales),'Scale restore'))
        if cleanup_failures:
            report['status']='failed'; report['restoration_failures']=cleanup_failures
        else:
            report['checks']['temporary_configuration_and_scales_restored'] = True
        report['elapsed_seconds']=round(time.monotonic()-started,2)
        Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='passed' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context',default=lab.CONTEXT); parser.add_argument('--namespace',default=lab.NAMESPACE)
    parser.add_argument('--report',required=True); args=parser.parse_args()
    lab.validate_scope(args.context,args.namespace)
    if (Path.home()/'.minikube/profiles/fhs-test').is_dir(): return local(args)
    ssh=['ssh','-F','/home/dragonlord/.ssh/config','-o','ConnectTimeout=5','dragonvm']
    lab.run(ssh+['true'],timeout=15)
    remote=lab.run(ssh+['mktemp -d /tmp/fhs-landing-acceptance.XXXXXXXX'],timeout=15).decode().strip()
    lab.require(remote.startswith('/tmp/fhs-landing-acceptance.') and '\n' not in remote,'Remote work directory')
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w:gz') as tar:
        for relative in ('platform/charts/fhs-platform','ops/platform/landing-page',
                         'ops/platform/discovery-portal-setup/acceptance.py'):
            for file in ([ROOT/relative] if (ROOT/relative).is_file() else (ROOT/relative).rglob('*')):
                if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
                    lab.require(file.name not in ('site-values.yaml','lab-values.yaml'), 'Private values in transfer sources')
                    tar.add(file,arcname=str(file.relative_to(ROOT)),recursive=False)
    lab.run(ssh+['tar -xzf - -C '+shlex.quote(remote)],data=archive.getvalue(),timeout=120)
    command=('cd '+shlex.quote(remote)+' && PATH=/home/dragon-lord/.local/bin:$PATH python3 '
             'ops/platform/landing-page/acceptance.py --context fhs-test '
             '--namespace fhs-discovery-portal-test --report '+shlex.quote(remote+'/report.json'))
    result=subprocess.run(ssh+[command],capture_output=True,timeout=3300)
    Path(args.report).write_bytes(lab.run(ssh+['cat '+shlex.quote(remote+'/report.json')],timeout=20))
    return result.returncode


if __name__=='__main__':
    try: sys.exit(main())
    except Exception as error:
        if '--report' in sys.argv:
            Path(sys.argv[sys.argv.index('--report')+1]).write_text(json.dumps({
                'status':'failed','failure':{'type':type(error).__name__,
                'stage':'scope, transport or remote execution; private diagnostics retained'}})+'\n')
        sys.exit(1)
