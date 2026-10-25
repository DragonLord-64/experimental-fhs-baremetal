#!/usr/bin/env python3
"""Controller-only discovery completion entrypoint; no physical hardware contact.

Reuses the retained delivered-chart release on dragonvm fhs-test. Does not create
clusters, change controller runs, or deploy. Missing prerequisites fail explicitly.
Private logs remain outside the repository; reports contain selected assertions.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import socket
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).parent
CONTEXT='fhs-test'
NAMESPACE='fhs-inventory-alignment'
RELEASE='fhs-inventory-alignment'
K=['minikube','-p',CONTEXT,'kubectl','--','--context='+CONTEXT]
SSH=['ssh','-F','/home/dragonlord/.ssh/config','-o','ConnectTimeout=5','dragonvm']


def run(argv, *, data=None, timeout=120, work=None):
    result=subprocess.run([str(v) for v in argv],input=data,capture_output=True,timeout=timeout)
    if result.returncode:
        if work:
            path=Path(work)/('private-command-'+str(time.time_ns())+'.log')
            path.write_bytes(result.stdout+b'\n'+result.stderr);path.chmod(0o600)
        raise RuntimeError(Path(str(argv[0])).name+' failed with exit '+str(result.returncode)+'; inspect private diagnostics')
    return result.stdout


def kubectl(*argv,work=None): return run(K+['-n',NAMESPACE]+list(argv),work=work)
def get(kind,name=None,work=None):return json.loads(kubectl('get',kind,*([name] if name else []),'-o','json',work=work))


def local(args):
    from discovery_native import Native, require
    work=Path(tempfile.mkdtemp(prefix='fhs-discovery-completion-'));work.chmod(0o700)
    report=dict(status='failed',context=CONTEXT,namespace=NAMESPACE,checks={},private_evidence_directory=str(work),
                limitations=['Synthetic fixtures and installed software only; physical hardware unverified.',
                             'Authenticated plugin pages use Django Client; no browser visual QA.'])
    forward=None;stage='inspect preserved pipeline state and services'
    try:
        # Inspection precedes all acceptance object writes; no process mutation.
        processes=subprocess.run(['pgrep','-f','ops/agent-pipeline'],capture_output=True,text=True,timeout=10)
        report['pipeline_processes_observed']=len(processes.stdout.splitlines())
        services=json.loads(run(K+['get','services','-A','-o','json'],work=work))
        pods=get('pods',work=work)['items']
        report['checks']['preserved_services_inspected']=len(services['items'])
        require(any(p['metadata']['name'].startswith('fhs-netbox-') and p['status'].get('phase')=='Running' for p in pods),'Retained NetBox service missing')
        release=json.loads(run(['helm','--kube-context',CONTEXT,'list','-n',NAMESPACE,'-o','json'],work=work))
        active=[r for r in release if r['name']==RELEASE]
        require(len(active)==1 and active[0]['chart'].startswith('fhs-platform-') and active[0]['status']=='deployed','Expected delivered fhs-platform release not deployed')
        report['retained_release']={k:active[0][k] for k in ('name','revision','chart','status')}
        report['delivered_chart_source_sha256']=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'platform/charts/fhs-platform').rglob('*')) if p.is_file())).hexdigest()
        def retained():
            return {kind:{p['metadata']['name']:(p['metadata']['uid'],p['spec'].get('volumeName')) for p in get(kind,work=work)['items']} for kind in ('pvc',)}
        baseline=retained()
        stage='real Ansible syntax routing and focused discovery fixtures'
        # The controller calls this once. Missing dependencies/skips fail rather
        # than substituting unit-only results for native acceptance.
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',ANSIBLE_NOCOLOR='1')
        result=subprocess.run([sys.executable,'-m','unittest','test_routing','test_task_flow','test_topology','test_discovery'],
            cwd=HERE,env=env,capture_output=True,text=True,timeout=300)
        (work/'private-fixture-tests.log').write_text(result.stdout+result.stderr);(work/'private-fixture-tests.log').chmod(0o600)
        require(result.returncode==0 and 'skipped=' not in result.stderr and 'SKIP' not in result.stderr,'Focused fixture tests failed or skipped')
        report['checks']['routing_discovery_fixtures']=True
        dummy=work/'syntax-credentials.yml';dummy.write_text('netbox_url: https://syntax.invalid\nnetbox_token: synthetic-syntax-only\n');dummy.chmod(0o600)
        run(['ansible-playbook','-i','localhost,',ROOT/'playbooks/netbox/netbox_import.yml','--syntax-check','-e',
             'netbox_credentials_file='+str(dummy)],timeout=60,work=work)
        report['checks']['real_ansible_syntax']=True
        stage='protected credentials and retained service forward'
        secret=get('secret','fhs-platform-credentials',work=work)
        token=base64.b64decode(secret['data']['api_token']).decode()
        credentials_digest=hashlib.sha256(json.dumps(secret['data'],sort_keys=True).encode()).hexdigest()
        deployment=get('deployment','fhs-netbox',work=work)
        # Discover configured base path from the readiness route, not screenshot IPs.
        container=next(c for c in deployment['spec']['template']['spec']['containers'] if c['name']=='netbox')
        probe=container.get('readinessProbe',{}).get('httpGet',{}).get('path','')
        require(probe.endswith('/login/'),'Cannot establish retained NetBox base path from readiness probe')
        base_path=probe[:-len('/login/')]
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        log=open(work/'private-forward.log','wb')
        forward=subprocess.Popen(K+['-n',NAMESPACE,'port-forward','service/fhs-netbox',str(port)+':80','--address=127.0.0.1'],stdout=log,stderr=log)
        for _ in range(60):
            require(forward.poll() is None,'Retained port forward exited')
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=1):break
            except OSError:time.sleep(1)
        else:raise RuntimeError('Retained port forward timed out')
        stage='native collector importer metadata cabling placement and power scenarios'
        native=Native('http://127.0.0.1:'+str(port)+base_path,token,work,report);native.run()
        stage='authenticated Topology Views and Inventory asset behavior'
        expected={key:report[key] for key in ('fixture_prefix','device_ids','topology_expected_pairs','network_cable_ids')}
        require(len(expected['network_cable_ids'])==9,'Expected seven LLDP and two verified physical DAC cables')
        code=(HERE/'probe_discovery.py').read_text()+'\nprint("FHS_DISCOVERY_PLUGIN="+json.dumps(probe('+repr(expected)+')))\n'
        output=run(K+['-n',NAMESPACE,'exec','deployment/fhs-netbox','-c','netbox','-i','--',
            '/opt/netbox/venv/bin/python','/opt/netbox/netbox/manage.py','shell','--interface','python'],data=code.encode(),timeout=120,work=work).decode()
        markers=[line.split('FHS_DISCOVERY_PLUGIN=',1)[1] for line in output.splitlines() if line.startswith('FHS_DISCOVERY_PLUGIN=')]
        require(len(markers)==1,'Authenticated plugin probe did not emit evidence')
        report['checks']['authenticated_plugins']=json.loads(markers[0])
        stage='preserved lab state and credentials'
        require(retained()==baseline,'Retained PVC bindings changed')
        current=get('secret','fhs-platform-credentials',work=work)
        require(hashlib.sha256(json.dumps(current['data'],sort_keys=True).encode()).hexdigest()==credentials_digest,'Protected credentials changed')
        report['checks']['retained_storage_and_credentials_preserved']=True
        report['status']='passed'
    except Exception as error:
        # Stack traces can contain response bodies; retain privately only.
        import traceback
        path=work/'private-failure.log';path.write_text(traceback.format_exc());path.chmod(0o600)
        report['failure']=dict(stage=stage,type=type(error).__name__,reason=str(error) if isinstance(error,AssertionError) else 'Inspect private diagnostic log')
    finally:
        if forward:
            forward.terminate()
            try:forward.wait(timeout=10)
            except subprocess.TimeoutExpired:forward.kill();forward.wait()
        Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='passed' else 1


def remote(args):
    # Reachability recovery is explicit and bounded, preserving both host OSes.
    try:run(SSH+['true'],timeout=15)
    except RuntimeError:
        run(['bash','/home/dragonlord/wol.sh'],timeout=15)
        time.sleep(60)
        run(SSH+['true'],timeout=15)
    remote=run(SSH+['mktemp -d /tmp/fhs-discovery-completion-src.XXXXXXXX'],timeout=15).decode().strip()
    if not remote.startswith('/tmp/fhs-discovery-completion-src.') or '\n' in remote:raise ValueError('Invalid remote workspace')
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w:gz') as tar:
        # No evidence originals, .git, controller/runs, credentials or emulator work.
        for directory in ('playbooks/netbox','ops/platform/inventory-alignment','platform/charts/fhs-platform'):
            for path in sorted((ROOT/directory).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.log'):
                    tar.add(path,arcname=str(path.relative_to(ROOT)),recursive=False)
    run(SSH+['tar -xzf - -C '+shlex.quote(remote)],data=archive.getvalue(),timeout=60)
    command='cd '+shlex.quote(remote)+' && PATH=/home/dragon-lord/.local/bin:$PATH PYTHONDONTWRITEBYTECODE=1 python3 ops/platform/inventory-alignment/acceptance_discovery.py --local --report '+shlex.quote(remote+'/report.json')
    result=subprocess.run(SSH+[command],capture_output=True,timeout=1740)
    Path(args.report).write_bytes(run(SSH+['cat '+shlex.quote(remote+'/report.json')],timeout=20))
    return result.returncode


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--dragonvm',action='store_true');mode.add_argument('--local',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--report',required=True);args=parser.parse_args()
    try:return remote(args) if args.dragonvm else local(args)
    except Exception as error:
        Path(args.report).write_text(json.dumps(dict(status='failed',failure=dict(stage='reachability or remote handoff',type=type(error).__name__),
            limitations=['No native acceptance pass established; inspect private remote diagnostics.']))+'\n')
        return 1


if __name__=='__main__':sys.exit(main())
