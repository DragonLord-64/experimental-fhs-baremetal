#!/usr/bin/env python3
"""Supervisor-only owned fixture reset/removal/reapply and restoration proof."""
import json
import subprocess
from pathlib import Path
from integration import H, ROOT
from topology import configured
from verify import K


def values(release):
    return json.loads(subprocess.check_output(H + ['get', 'values', release, '-o', 'json']))


def main():
    # Keep only in memory: original release values may contain private settings.
    originals = {name: json.loads((ROOT / '.runtime' / (name + '-before.json')).read_text())
                 for name in ('prometheus', 'telegraf')}
    subprocess.run([str(ROOT / 'deploy.sh'), 'reset'], check=True)
    logs = subprocess.check_output(K + ['-n', 'fhs-emulators', 'logs',
                                         'deployment/cisco-emulator', '-c', 'cisco'], text=True)
    assert f"sent collection 0 ({len(configured()['switches'])} switches)" in logs, 'Sender did not restart collection sequence'
    subprocess.run([str(ROOT / 'deploy.sh'), 'down'], check=True)
    namespace = subprocess.check_output(K + ['get', 'namespace', 'fhs-emulators', '--ignore-not-found', '-o', 'name'], text=True)
    assert not namespace.strip(), 'Owned namespace remains'
    prom, telegraf = values('prometheus'), values('telegraf')
    jobs = prom['serverFiles']['prometheus.yml']['scrape_configs']
    assert not any(j['job_name'] in ('fhs-emulator', 'node-emulator') for j in jobs)
    assert jobs == originals['prometheus']['serverFiles']['prometheus.yml']['scrape_configs'], 'Original scrape jobs changed'
    # No unrelated operator writes are allowed during this scoped lifecycle proof.
    assert telegraf['config'] == originals['telegraf']['config'], 'Telegraf configuration did not restore exactly'
    assert all(not (ROOT / '.runtime' / (n + '-before.json')).exists() for n in originals)
    print('PASS reset collection sequence, owned namespace removal, original scrape jobs and exact Telegraf config restored', flush=True)
    subprocess.run(['python3', str(ROOT / 'platform-check.py')], check=True)
    subprocess.run([str(ROOT / 'deploy.sh'), 'apply'], check=True)
    subprocess.run(['python3', str(ROOT / 'platform-check.py')], check=True)
    print('PASS existing-image reapply and full live verification after cleanup', flush=True)


if __name__ == '__main__':
    main()
