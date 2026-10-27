"""Container-local installation assertions only; never request exporter metrics."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

names = ('prometheus', 'node', 'fhs-exporter', 'filebeat')
counts = {}
for name in names:
    service = json.loads(Path('/tmp/service-' + name + '.json').read_text())
    assert service['enabled'], name
    assert Path('/proc/' + str(service['pid']) + '/stat').read_text().split()[2] != 'Z', name
    counts[name] = service['starts']
for f, mode in [('/etc/filebeat/filebeat.yml', 0o600), ('/etc/prometheus/prometheus.yml', 0o640), ('/etc/prometheus/site.yml', 0o640)]:
    st = Path(f).stat()
    assert st.st_uid == 0 and stat.S_IMODE(st.st_mode) == mode, f
for f in ('/usr/local/bin/prometheus', '/opt/venvs/fhs-exporter', '/opt/venvs/fhs-exporter/bin/fhs-prometheus-exporter'):
    st = Path(f).stat()
    assert st.st_uid == 0 and not (st.st_mode & 0o022), f
# Explicit real binary validation, without service or application API requests.
prom = next(l.split('=', 1)[1].split()[0] for l in Path('/etc/systemd/system/prometheus.service').read_text().splitlines() if l.startswith('ExecStart='))
promtool = str(Path(prom).with_name('promtool'))
for args in ([promtool, 'check', 'config', '/etc/prometheus/prometheus.yml'], [promtool, 'check', 'web-config', '/etc/prometheus/site.yml'], ['/usr/share/filebeat/bin/filebeat', 'test', 'config', '--path.home', '/usr/share/filebeat', '--path.data', '/var/lib/filebeat', '-c', '/etc/filebeat/filebeat.yml'], ['/opt/venvs/fhs-exporter/bin/fhs-prometheus-exporter', '--help']):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
# Real service child identity; no success inferred solely from manager state.
for name, comm, root in [('prometheus', 'prometheus', False), ('node', 'node_exporter', False), ('fhs-exporter', 'python', True), ('filebeat', 'filebeat', True)]:
    parent = json.loads(Path('/tmp/service-' + name + '.json').read_text())['pid']
    children = Path(f'/proc/{parent}/task/{parent}/children').read_text().split()
    assert children, name
    statuses = [Path('/proc/' + pid + '/status').read_text() for pid in children]
    uids = [int(next(l for l in s.splitlines() if l.startswith('Uid:')).split()[1]) for s in statuses]
    assert all((uid == 0) == root for uid in uids), (name, uids)
checkpoint = Path('/tmp/stage5-counts.json')
if '--snapshot' in sys.argv:
    checkpoint.write_text(json.dumps(counts))
elif '--unchanged' in sys.argv:
    assert counts == json.loads(checkpoint.read_text()), counts
elif any(v in sys.argv for v in ('--upgraded', '--recovered', '--exporter-repaired')):
    old = json.loads(checkpoint.read_text())
    expected = {k: v + (1 if '--recovered' in sys.argv or ('--exporter-repaired' in sys.argv and k == 'fhs-exporter') or ('--upgraded' in sys.argv and k in ('prometheus', 'node')) else 0) for k, v in old.items()}
    assert counts == expected, (counts, expected)
    checkpoint.write_text(json.dumps(counts))
print('real install/config/permissions/process checks passed; starts=' + json.dumps(counts, sort_keys=True))
