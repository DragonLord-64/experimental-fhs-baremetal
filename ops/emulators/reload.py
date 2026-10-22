#!/usr/bin/env python3
"""Reload the lab Prometheus only after its projected ConfigMap is current."""
import hashlib
import json
import re
import subprocess
import urllib.request
import yaml

from verify import K, forward, get, retry

NAMESPACE = 'fhs-platform'
SERVICE = 'monitoring-prometheus'


def job_names(config):
    # Prometheus's rendered YAML uses a scalar job_name on its own line.
    return set(re.findall(r'^\s*(?:-\s*)?job_name:\s*[\"\']?([^\s\"\']+)[\"\']?\s*$', config, re.MULTILINE))


def reload_config():
    cm = json.loads(subprocess.check_output(K + ['-n', NAMESPACE, 'get', 'configmap', SERVICE, '-o', 'json']))
    desired = cm['data']['prometheus.yml']
    expected = job_names(desired)
    if not expected:
        raise RuntimeError('Refusing reload: no scrape jobs in the expected ConfigMap')
    digest = hashlib.sha256(desired.encode()).digest()

    def mounted():
        data = subprocess.check_output(K + ['-n', NAMESPACE, 'exec', 'deployment/' + SERVICE,
                                              '-c', 'prometheus-server', '--', 'cat', '/etc/config/prometheus.yml'])
        if hashlib.sha256(data).digest() != digest:
            raise RuntimeError('Waiting for Prometheus projected ConfigMap update')
    retry(mounted, 180)
    with forward(NAMESPACE, SERVICE, 9090) as port:
        request = urllib.request.Request(f'http://127.0.0.1:{port}/-/reload', data=b'', method='POST')
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError('Prometheus rejected configuration reload')
        loaded = json.loads(get(port, '/api/v1/status/config'))
        if loaded.get('status') != 'success' or job_names(loaded['data']['yaml']) != expected:
            raise RuntimeError('Prometheus loaded scrape jobs differ from the ConfigMap')
        # Job names alone cannot detect a stale full/reduced inventory.
        desired_jobs = yaml.safe_load(desired).get('scrape_configs', [])
        loaded_jobs = {j['job_name']: j for j in yaml.safe_load(loaded['data']['yaml']).get('scrape_configs', [])}
        for job in desired_jobs:
            if loaded_jobs[job['job_name']].get('static_configs', []) != job.get('static_configs', []):
                raise RuntimeError('Prometheus loaded static targets/labels differ from the ConfigMap')
    print('PASS Prometheus projected config current, reload accepted, loaded scrape jobs and static targets match', flush=True)


if __name__ == '__main__':
    reload_config()
