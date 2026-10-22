#!/usr/bin/env python3
"""Supervisor-only read-only serving diagnostics; whitelist output, no secrets."""
import json
import subprocess

from live import K


def kubectl(*args):
    return subprocess.check_output(K + list(args), stderr=subprocess.DEVNULL,
                                   timeout=40, text=True)


PROBE = r'''
import collections, json, os, re
from pathlib import Path
counts = collections.Counter()
flags = []
rss_kib = 0
for process in Path('/proc').glob('[0-9]*'):
    try:
        command = (process / 'cmdline').read_bytes().split(b'\0')
        text = b' '.join(command).decode(errors='replace')
        # Do not print command lines: they can contain credentials.
        for server in ('gunicorn', 'uwsgi', 'unitd', 'granian'):
            if server in text and 'import collections' not in text:
                counts[server] += 1
                flags.extend(re.findall(r'--(workers|threads|worker-connections|max-requests)[= ]+(\d+)\b', text))
        status = (process / 'status').read_text()
        match = re.search(r'^VmRSS:\s+(\d+)', status, re.M)
        if match:
            rss_kib += int(match[1])
    except (OSError, ValueError):
        pass
memory = {}
for name in ('memory.current', 'memory.max', 'memory.peak', 'memory.events'):
    path = Path('/sys/fs/cgroup') / name
    if path.exists():
        value = path.read_text().strip()
        if re.fullmatch(r'[a-z0-9_\s]+', value):
            memory[name] = value
numeric_settings = {}
for filename in ('/etc/netbox/gunicorn.py', '/opt/netbox/gunicorn.py', '/etc/netbox/config/gunicorn.py'):
    path = Path(filename)
    if path.is_file():
        for key, value in re.findall(r'^\s*(workers|threads|max_requests|timeout)\s*=\s*(\d+)\s*$', path.read_text(), re.M):
            numeric_settings[key] = int(value)
numeric_environment = {}
for name in ('WEB_CONCURRENCY', 'GRANIAN_WORKERS', 'GRANIAN_THREADS',
             'GRANIAN_BLOCKING_THREADS', 'CACHE_TIMEOUT'):
    value = os.environ.get(name, '')
    if value.isdecimal():
        numeric_environment[name] = int(value)
cache_environment_present = {name: bool(os.environ.get(name)) for name in
    ('REDIS_HOST', 'REDIS_CACHE_HOST', 'REDIS_DATABASE', 'REDIS_CACHE_DATABASE')}
print(json.dumps({'server_process_counts': dict(counts), 'numeric_server_flags': flags,
                  'numeric_gunicorn_settings': numeric_settings,
                  'numeric_environment': numeric_environment,
                  'cache_environment_present': cache_environment_present,
                  'process_rss_sum_kib': rss_kib, 'cgroup': memory}))
'''


def main():
    pods = json.loads(kubectl('get', 'pods', '-l', 'app.kubernetes.io/instance=netbox', '-o', 'json'))
    found = False
    for pod in pods['items']:
        containers = pod['spec']['containers']
        for container in containers:
            if container['name'] != 'netbox':
                continue
            found = True
            status = next(s for s in pod['status']['containerStatuses'] if s['name'] == 'netbox')
            previous = status.get('lastState', {}).get('terminated', {})
            print(json.dumps({'resources': container.get('resources'), 'ready': status['ready'],
                'restart_count': status['restartCount'],
                'previous_termination': {k: previous[k] for k in ('reason', 'exitCode', 'finishedAt') if k in previous},
                'cache_env_names': sorted(e['name'] for e in container.get('env', [])
                                          if any(s in e['name'] for s in ('CACHE', 'REDIS', 'VALKEY')))}), flush=True)
            result = kubectl('exec', pod['metadata']['name'], '-c', 'netbox', '--',
                             'python', '-c', PROBE)
            # Accept only the probe's JSON, never arbitrary command output.
            print(json.dumps(json.loads(result)), flush=True)
    if not found:
        raise RuntimeError('NetBox serving container not found')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Read-only serving diagnostics failed; private output suppressed')
