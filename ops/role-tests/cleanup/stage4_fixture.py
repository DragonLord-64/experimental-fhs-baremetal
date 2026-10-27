"""Tiny controller archives; real Poetry installs them, no SDK/application probes.

systemctl implements ONLY the module calls needed by this fixture, running real
stand-in console processes as the unit user. It does not establish systemd behavior.
"""
from pathlib import Path
import tarfile

base = Path('/tmp/fixtures')
Path('/tmp/archives').mkdir(exist_ok=True)
for kind in ('fsp', 'vcc'):
    p = base / f'fixture-{kind}'
    p.mkdir(parents=True, exist_ok=True)
    (p/'pyproject.toml').write_text(f'''[tool.poetry]
name = "fixture-{kind}"
version = "1.0.0"
description = "installation fixture"
authors = ["Fixture <fixture@example.invalid>"]
packages = [{{include = "server.py"}}]
[tool.poetry.dependencies]
python = ">=3.10,<4"
[tool.poetry.scripts]
ska-mid-cbf-fhs-{kind}-grpc-controller = "server:run"
[build-system]
requires = ["poetry-core>=2.0.0,<3"]
build-backend = "poetry.core.masonry.api"
''')
    (p/'server.py').write_text(f'''import argparse, socket

def run():
    p = argparse.ArgumentParser()
    for option in ('devices', 'regions', 'cards'):
        p.add_argument('--'+option, nargs='+', required=True)
    for option in ('host','port','bitstream_pkg_path','log'):
        p.add_argument('--'+option, required=True)
    p.add_argument('--emulation_mode', action='store_true')
    a = p.parse_args()
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((a.host, int(a.port))); s.listen()
        while True:
            c, _ = s.accept(); c.sendall(b'{kind}'); c.close()
''')
    d = base/'fixture-bitstream'/'raw'/kind/'drivers'
    d.mkdir(parents=True, exist_ok=True)
with tarfile.open('/tmp/archives/fixture-bitstream.tar.gz', 'w:gz') as t:
    t.add(base/'fixture-bitstream', arcname='fixture-bitstream')
bist = base/'fixture-bist'
bist.mkdir(exist_ok=True)
(bist/'requirements.txt').write_text('# No application dependencies in installation fixture.\n')
with tarfile.open('/tmp/archives/fixture-bist.tar.gz', 'w:gz') as t:
    t.add(bist/'requirements.txt', arcname='requirements.txt')
Path('/run/systemd/system').mkdir(parents=True, exist_ok=True)
Path('/usr/bin/systemctl').write_text('''#!/usr/bin/python3
import json, os, shlex, signal, subprocess, sys, time
from pathlib import Path
a = [v for v in sys.argv[1:] if not v.startswith('-')]
cmd = a[0]
unit = a[-1].removesuffix('.service')
p = Path('/tmp/service-'+unit+'.json')
s = json.loads(p.read_text()) if p.exists() else {'enabled':False,'pid':None,'starts':0}
active = s['pid'] is not None
if cmd == 'show':
    print('LoadState=loaded\\nActiveState='+('active' if active else 'inactive')+'\\nSubState=running\\nUnitFileState='+('enabled' if s['enabled'] else 'disabled'))
elif cmd == 'is-enabled':
    print('enabled' if s['enabled'] else 'disabled'); sys.exit(0 if s['enabled'] else 1)
elif cmd in ('enable','disable'):
    s['enabled'] = cmd == 'enable'
elif cmd in ('start','restart','stop'):
    if active and cmd in ('stop','restart'):
        os.kill(s['pid'],signal.SIGTERM); s['pid']=None; time.sleep(.1)
    if cmd in ('start','restart') and s['pid'] is None:
        text = Path('/etc/systemd/system/'+unit+'.service').read_text().splitlines()
        user = next(v.split('=',1)[1] for v in text if v.startswith('User='))
        argv = shlex.split(next(v.split('=',1)[1] for v in text if v.startswith('ExecStart=')))
        env = os.environ.copy()
        for line in text:
            if line.startswith('Environment='):
                k,v = shlex.split(line.split('=',1)[1])[0].split('=',1); env[k]=v
        cwd = next(v.split('=',1)[1] for v in text if v.startswith('WorkingDirectory='))
        with open('/tmp/'+unit+'.log','a') as log:
            proc = subprocess.Popen(['/usr/sbin/runuser','-u',user,'--']+argv, cwd=cwd, env=env, stdout=log, stderr=log, start_new_session=True)
        s['pid']=proc.pid; s['starts']+=1; time.sleep(.3)
elif cmd not in ('daemon-reload','reset-failed'):
    raise SystemExit('unsupported fixture systemctl call: '+repr(a))
p.write_text(json.dumps(s))
''')
Path('/usr/bin/systemctl').chmod(0o755)
