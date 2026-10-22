#!/usr/bin/env python3
"""Apply owned fixtures; migrate only an unchanged client-side ConfigMap."""
import json
from pathlib import Path
import subprocess

from verify import K


def check_configmap(current, desired, managed=False):
    if not current:
        return
    if current['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != 'fhs-emulators':
        raise RuntimeError('Fixture ConfigMap lacks ownership label')
    if managed or current['data'] == desired['data']:
        return
    prior = current['metadata'].get('annotations', {}).get('kubectl.kubernetes.io/last-applied-configuration')
    if not prior or json.loads(prior).get('data') != current['data']:
        raise RuntimeError('Fixture ConfigMap changed outside recorded apply; manual review required')


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / '.runtime/rendered.json').read_text())
    fixture = next(d for d in manifest['items'] if d['kind'] == 'ConfigMap')
    observed = subprocess.check_output(K + ['-n', 'fhs-emulators', 'get', 'configmap', 'monitoring-fixtures', '--ignore-not-found', '--show-managed-fields=true', '-o', 'json'], text=True)
    current = json.loads(observed) if observed.strip() else None
    # A prior SSA install has no client-side baseline; the SSA manager owns its
    # data already. Do not force anything on subsequent updates.
    managed = current and any(m.get('manager') == 'fhs-emulators' and m.get('operation') == 'Apply'
                              for m in current['metadata'].get('managedFields', []))
    check_configmap(current, fixture, managed=managed)
    if current:
        fixture['metadata']['resourceVersion'] = current['metadata']['resourceVersion']
    fixtures = root / '.runtime/fixtures-apply.json'
    workloads = root / '.runtime/workloads-apply.json'
    fixtures.write_text(json.dumps(fixture))
    workloads.write_text(json.dumps(dict(manifest, items=[d for d in manifest['items'] if d['kind'] != 'ConfigMap'])))
    commands = [K + ['apply', '--server-side', '--field-manager=fhs-emulators'] +
                (['--force-conflicts'] if current and not managed else []) + ['-f', str(fixtures)],
                K + ['apply', '--server-side', '--field-manager=fhs-emulators', '-f', str(workloads)]]
    for command in commands:
        subprocess.run(command + ['--dry-run=server'], check=True)
    for command in commands:
        subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
