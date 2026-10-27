"""Stage-4 minimal service boundary adapted to real stage-5 binaries.

No systemd claim. No metrics requests or hardware collectors: Prometheus runs an
empty scrape config after the actual deployed config is validated separately.
"""
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

a = [v for v in sys.argv[1:] if not v.startswith('-')]
cmd = a[0]
unit = a[-1].removesuffix('.service')
p = Path('/tmp/service-' + unit + '.json')
s = json.loads(p.read_text()) if p.exists() else {'enabled': False, 'pid': None, 'starts': 0}
active = False
if s['pid']:
    try:
        active = Path('/proc/' + str(s['pid']) + '/stat').read_text().split()[2] != 'Z'
    except FileNotFoundError:
        pass
if cmd in ('list-units', 'list-unit-files'):
    for name in ('prometheus', 'node', 'fhs-exporter', 'filebeat'):
        if Path('/etc/systemd/system/' + name + '.service').exists():
            if cmd == 'list-units':
                print(name + '.service loaded active running fixture')
            else:
                print(name + '.service enabled')
    sys.exit(0)
if cmd == 'show':
    print('LoadState=loaded\nActiveState=' + ('active' if active else 'inactive') + '\nSubState=' + ('running' if active else 'dead') + '\nUnitFileState=' + ('enabled' if s['enabled'] else 'disabled'))
elif cmd == 'is-enabled':
    print('enabled' if s['enabled'] else 'disabled')
    sys.exit(0 if s['enabled'] else 1)
elif cmd in ('enable', 'disable'):
    s['enabled'] = cmd == 'enable'
elif cmd in ('start', 'restart', 'stop'):
    if active and cmd in ('stop', 'restart'):
        os.killpg(s['pid'], signal.SIGTERM)
        time.sleep(.5)
        active = False
    if cmd in ('start', 'restart') and not active:
        path = Path('/etc/systemd/system/' + unit + '.service')
        if not path.exists():
            path = Path('/usr/lib/systemd/system/' + unit + '.service')
        text = path.read_text().replace('\\\n', '').splitlines()
        argv = shlex.split(next(v.split('=', 1)[1] for v in text if v.startswith('ExecStart=')))
        # Never let real Prometheus scrape the hardware exporter in this fixture.
        if unit == 'prometheus':
            argv = [v for v in argv if not v.startswith('--config.file=')]
            argv.append('--config.file=/tmp/no-scrapes.yml')
        if unit == 'filebeat':
            argv = ['/usr/share/filebeat/bin/filebeat', '-e', '-c', '/etc/filebeat/filebeat.yml', '--path.home', '/usr/share/filebeat']
        user = next((v.split('=', 1)[1] for v in text if v.startswith('User=')), 'root')
        env = os.environ.copy()
        for line in text:
            if line.startswith('Environment='):
                k, v = shlex.split(line.split('=', 1)[1])[0].split('=', 1)
                env[k] = v
        with open('/tmp/' + unit + '.log', 'a') as log:
            proc = subprocess.Popen(['/usr/sbin/runuser', '-u', user, '--'] + argv, env=env, stdout=log, stderr=log, start_new_session=True)
        s['pid'] = proc.pid
        s['starts'] += 1
        time.sleep(.5)
        if proc.poll() is not None:
            raise SystemExit('service process failed; see /tmp/' + unit + '.log')
    elif cmd == 'stop':
        s['pid'] = None
elif cmd not in ('daemon-reload', 'reset-failed'):
    raise SystemExit('unsupported fixture systemctl call: ' + repr(a))
p.write_text(json.dumps(s))
