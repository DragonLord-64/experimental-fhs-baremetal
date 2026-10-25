#!/usr/bin/env python3
"""Controller-only bounded delivered-chart smoke on the retained fhs-test release."""
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('lab', ROOT/'ops/platform/discovery-portal-setup/acceptance.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def local(args):
    started = time.monotonic()
    report = {'status': 'failed', 'checks': {}, 'limitations': [
        'Synthetic cable only; no physical discovery.', 'Authenticated page uses Django test client; assets use HTTP.']}
    class BoundedLab(lab.Acceptance):
        def kubectl(self, *parts, obj=None, namespace=True):
            command = self.k + (['-n', lab.NAMESPACE] if namespace else []) + list(parts)
            return lab.run(command, data=json.dumps(obj).encode() if obj is not None else None,
                           timeout=650 if parts[0] == 'rollout' else 90)
    check = BoundedLab(args.report)
    diagnostics = check.work/'diagnostics'
    os.environ.setdefault('FHS_ACCEPTANCE_DIAGNOSTICS', str(diagnostics))
    report['diagnostics_directory'] = os.environ['FHS_ACCEPTANCE_DIAGNOSTICS']
    scales = []
    cronjobs = []
    stage = 'inspect retained services and release'
    try:
        services = check.get('services', namespace=False)['items']
        report['checks']['services_inspected'] = len(services)
        ns = check.get('namespace', lab.NAMESPACE, namespace=False)
        lab.require(ns['metadata'].get('labels', {}).get('fhs-acceptance-owner') == lab.OWNER, 'Namespace owner mismatch')
        def retained_state():
            return {kind: {o['metadata']['name']: (o['metadata']['uid'],
                    lab.digest(o.get('data', {})) if kind == 'secrets' else o['spec'].get('volumeName'))
                    for o in check.get(kind)['items']
                    if kind != 'secrets' or o.get('type') != 'helm.sh/release.v1'}
                    for kind in ('pvc', 'secrets')}
        retained = retained_state()
        cronjobs = [(o['metadata']['name'], o['spec'].get('suspend', False))
                    for o in check.get('cronjobs')['items']]
        workloads = check.get('deployments,statefulsets')['items']
        scales = [(o['kind'].lower(), o['metadata']['name'], o['spec'].get('replicas', 1)) for o in workloads]
        required = {'fhs-netbox', 'fhs-netbox-worker', 'fhs-postgresql', 'fhs-valkey-primary'}
        lab.require(required <= {n for _, n, _ in scales}, 'Retained release consumers missing')
        # Preserve all unrelated desired scales; skip unrelated setup Jobs for this plugin-only smoke.
        renderer = check.work/'render.py'
        renderer.write_text('''#!/usr/bin/env python3
import sys,yaml
scales = ''' + repr({n: (1 if n in required else count) for _, n, count in scales}) + '''
for obj in yaml.safe_load_all(sys.stdin):
    if not obj or obj['kind'] == 'Job': continue
    if obj['kind'] in ('Deployment', 'StatefulSet'):
        obj['spec']['replicas'] = scales[obj['metadata']['name']]
    if obj['kind'] == 'CronJob': obj['spec']['suspend'] = True
    print(yaml.safe_dump(obj), end='---\\n')
''')
        renderer.chmod(0o700)
        values = Path('/tmp/fhs-discovery-acceptance-7fe5ixpb/lab-values.yaml')
        lab.require(values.is_file(), 'Retained private lab values missing')
        stage = 'upgrade delivered chart and wait for required consumers'
        upgrade = time.monotonic()
        lab.run(['helm', 'upgrade', lab.RELEASE, ROOT/'platform/charts/fhs-platform',
                 '--kube-context', lab.CONTEXT, '-n', lab.NAMESPACE, '-f', values,
                 '--post-renderer', renderer, '--timeout', '10m'], timeout=650)
        # All consumers start concurrently; web startup also waits for its databases.
        for kind, name, _ in sorted(scales, key=lambda row: row[1] != 'fhs-netbox'):
            if name in required:
                check.kubectl('rollout', 'status', kind+'/'+name,
                              '--timeout='+('600s' if name == 'fhs-netbox' else '60s'))
        report['checks']['upgrade_seconds'] = round(time.monotonic()-upgrade, 2)
        stage = 'verify version, migrations, authenticated topology and fixture edge'
        probe = (Path(__file__).with_name('probe.py')).read_text()
        before = time.monotonic()
        output = lab.run(
            check.k+['-n', lab.NAMESPACE, 'exec', 'deployment/fhs-netbox', '-c', 'netbox', '-i', '--',
                     '/opt/netbox/venv/bin/python', '/opt/netbox/netbox/manage.py', 'shell', '--interface', 'python'],
            data=probe.encode(), timeout=120)
        marker = next(line.split('FHS_TOPOLOGY_RESULT=', 1)[1] for line in output.decode().splitlines()
                      if line.startswith('FHS_TOPOLOGY_RESULT='))
        report['checks']['plugin'] = json.loads(marker)
        report['checks']['probe_seconds'] = round(time.monotonic()-before, 2)
        stage = 'fetch actual plugin CSS and JS over HTTP'
        with check.forward('fhs-netbox', 80) as origin:
            for asset in report['checks']['plugin']['assets']:
                # urllib request() decodes text; verify bytes and content type directly instead.
                from urllib.request import urlopen
                with urlopen(origin+asset['url'], timeout=30) as response:
                    body = response.read()
                    lab.require(response.status == 200 and len(body) == asset['bytes'], 'Static asset mismatch')
                    lab.require(('css' if asset['kind']=='css' else 'javascript') in response.headers['Content-Type'],
                                'Static content type mismatch')
                asset['http_verified'] = True
        stage = 'verify retained PVC and application credential identities'
        lab.require(retained_state() == retained, 'Retained PVC or credential identity changed')
        report['checks']['pvcs_and_credentials_preserved'] = True
        report['status'] = 'passed'
    except Exception as error:
        # Exception text/command output may contain private data: expose type only.
        report['failure'] = {'type': type(error).__name__, 'stage': stage}
    finally:
        try:
            for name, suspended in cronjobs:
                check.kubectl('patch', 'cronjob', name, '--type=merge',
                              '-p', json.dumps({'spec': {'suspend': suspended}}))
            for kind, name, count in scales:
                if name in {'fhs-netbox', 'fhs-netbox-worker', 'fhs-postgresql', 'fhs-valkey-primary'}:
                    check.kubectl('scale', kind+'/'+name, '--replicas='+str(count))
            report['checks']['original_scales_restored'] = all(
                o['spec'].get('replicas', 1) == count
                for kind, name, count in scales for o in [check.get(kind, name)])
            lab.require(report['checks']['original_scales_restored'], 'Scale restoration failed')
        except Exception:
            report['status'] = 'failed'
            report['restoration_failure'] = True
        report['elapsed_seconds'] = round(time.monotonic()-started, 2)
        Path(args.report).write_text(json.dumps(report, indent=2)+'\n')
    return 0 if report['status']=='passed' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--namespace', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    lab.validate_scope(args.context, args.namespace)
    if (Path.home()/'.minikube/profiles/fhs-test').is_dir():
        return local(args)
    ssh = ['ssh', '-F', '/home/dragonlord/.ssh/config', '-o', 'ConnectTimeout=5', 'dragonvm']
    lab.run(ssh+['true'], timeout=15)
    remote = lab.run(ssh+['mktemp -d /tmp/fhs-topology-smoke.XXXXXXXX'], timeout=15).decode().strip()
    lab.require(remote.startswith('/tmp/fhs-topology-smoke.') and '\n' not in remote, 'Invalid remote directory')
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w:gz') as tar:
        for relative in ('platform/charts/fhs-platform', 'ops/platform/topology-views',
                         'ops/platform/discovery-portal-setup/acceptance.py'):
            for file in ([ROOT/relative] if (ROOT/relative).is_file() else (ROOT/relative).rglob('*')):
                if file.is_file() and '__pycache__' not in file.parts:
                    tar.add(file, arcname=str(file.relative_to(ROOT)), recursive=False)
    lab.run(ssh+['tar -xzf - -C '+shlex.quote(remote)], data=archive.getvalue(), timeout=120)
    command = ('cd '+shlex.quote(remote)+' && PATH=/home/dragon-lord/.local/bin:$PATH python3 '
               'ops/platform/topology-views/smoke.py --context fhs-test '
               '--namespace fhs-discovery-portal-test --report '+shlex.quote(remote+'/report.json'))
    result = subprocess.run(ssh+[command], capture_output=True, timeout=2400)
    Path(args.report).write_bytes(lab.run(ssh+['cat '+shlex.quote(remote+'/report.json')], timeout=20))
    return result.returncode


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # Keep the controller report actionable without leaking SSH/Helm output.
        if '--report' in sys.argv:
            Path(sys.argv[sys.argv.index('--report')+1]).write_text(json.dumps({
                'status': 'failed', 'failure': {'type': type(error).__name__,
                'stage': 'scope, reachability or remote execution; inspect private runner diagnostics'}})+'\n')
        sys.exit(1)
