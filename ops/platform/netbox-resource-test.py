#!/usr/bin/env python3
"""Read-only lab web/API concurrency check; never changes inventory or services."""
import argparse
import base64
import json
import socket
import subprocess
import time
from urllib.request import Request, urlopen

K = ['minikube', '-p', 'fhs-test', 'kubectl', '--', '--context=fhs-test',
     '-n', 'fhs-platform', '--request-timeout=30s']
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--expected-devices', type=int)
args = parser.parse_args()


def k(*args):
    return subprocess.check_output(K + list(args), text=True)


def pod_state(name):
    pod = json.loads(k('get', 'pod', name, '-o', 'json'))
    status = next(x for x in pod['status']['containerStatuses'] if x['name'] == 'netbox')
    return {'uid': pod['metadata']['uid'], 'restarts': status['restartCount'],
            'last_termination': status.get('lastState', {}), 'ready': status['ready']}


deployment = json.loads(k('get', 'deployment', 'netbox', '-o', 'json'))
container = next(x for x in deployment['spec']['template']['spec']['containers'] if x['name'] == 'netbox')
env = {item['name']: item.get('value') for item in container['env']}
assert env['GRANIAN_WORKERS'] == '2'
assert container['resources']['limits']['memory'] == '2Gi'
selector = ','.join(f'{key}={value}' for key, value in deployment['spec']['selector']['matchLabels'].items())
pods = json.loads(k('get', 'pods', '-l', selector, '-o', 'json'))['items']
pod = next(x['metadata']['name'] for x in pods if not x['metadata'].get('deletionTimestamp'))
before = pod_state(pod)
assert before['ready']
token = base64.b64decode(json.loads(k('get', 'secret', 'netbox-superuser', '-o', 'json'))['data']['api_token']).decode()
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
forward = subprocess.Popen(K + ['port-forward', '--address=127.0.0.1', 'svc/netbox', f'{port}:80'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
shell = None


def api(path):
    request = Request(f'http://127.0.0.1:{port}/netbox/api/{path}',
                      headers={'Authorization': 'Token ' + token})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


try:
    for attempt in range(30):
        try:
            initial = api('status/')
            break
        except Exception:
            if forward.poll() is not None:
                raise RuntimeError('Port-forward exited')
            time.sleep(1)
    else:
        raise RuntimeError('API not ready')
    count = api('dcim/devices/?limit=1')['count']
    if args.expected_devices is not None:
        assert count == args.expected_devices
    shell = subprocess.Popen(K + ['exec', '-i', pod, '-c', 'netbox', '--',
        '/opt/netbox/venv/bin/python', '/opt/netbox/netbox/manage.py', 'shell',
        '--no-startup', '--no-imports', '--interface', 'python'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    shell.stdin.write("from dcim.models import Device\nimport json,time\nprint('RESOURCE_CHECK=' + json.dumps({'devices': Device.objects.count()}), flush=True)\ntime.sleep(8)\n")
    shell.stdin.close()
    overlapping = 0
    for request_number in range(30):
        assert api('status/')['plugins'] == initial['plugins']
        assert api('dcim/devices/?limit=1')['count'] == count
        overlapping += shell.poll() is None
        time.sleep(0.5)
    shell.wait(timeout=30)
    output = shell.stdout.read()
    assert shell.returncode == 0, 'Concurrent Django management command failed'
    facts = json.loads(next(line.removeprefix('RESOURCE_CHECK=') for line in output.splitlines()
                            if line.startswith('RESOURCE_CHECK=')))
    assert facts['devices'] == count
    assert overlapping > 0
    memory = k('exec', pod, '-c', 'netbox', '--', 'sh', '-c',
               'cat /sys/fs/cgroup/memory.current /sys/fs/cgroup/memory.peak /sys/fs/cgroup/memory.events')
    after = pod_state(pod)
    assert before == after, 'Pod state/restart counters changed during concurrent load'
    assert 'oom_kill 0' in memory
    print(json.dumps({'result': 'PASS', 'api_requests': 62, 'overlap_pairs': overlapping,
                      'devices': count, 'plugins': initial['plugins'], 'workers': 2,
                      'resources': container['resources'], 'before': before, 'after': after,
                      'cgroup_memory': memory}, indent=2))
finally:
    if shell is not None and shell.poll() is None:
        shell.terminate()
        shell.wait(timeout=10)
    forward.terminate()
    forward.wait(timeout=10)
