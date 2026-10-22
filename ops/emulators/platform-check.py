#!/usr/bin/env python3
"""Read-only application checks for the existing lab Grafana and NetBox."""
import base64
import json
import subprocess
import urllib.request

from verify import K, forward, get, retry


def secret(name):
    data = json.loads(subprocess.check_output(K + ['-n', 'fhs-platform', 'get', 'secret', name, '-o', 'json']))['data']
    return {k: base64.b64decode(v).decode() for k, v in data.items()}


def authenticated_get(port, path, authorization):
    request = urllib.request.Request(f'http://127.0.0.1:{port}{path}', headers={'Authorization': authorization})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def check_netbox():
    with forward('fhs-platform', 'netbox', 80) as netbox:
        token = secret('netbox-superuser')['api_token']
        status = authenticated_get(netbox, '/netbox/api/status/', 'Token ' + token)
        assert isinstance(status, dict) and status.get('netbox-version'), 'NetBox status is incomplete'
    print('PASS existing NetBox authenticated API status (read-only)', flush=True)


def check_grafana():
    with forward('fhs-platform', 'monitoring-grafana', 80) as grafana:
        assert json.loads(get(grafana, '/api/health'))['database'] == 'ok'
        credentials = secret('monitoring-grafana-admin')
        auth = 'Basic ' + base64.b64encode((credentials['admin-user'] + ':' + credentials['admin-password']).encode()).decode()
        result = authenticated_get(grafana, '/api/datasources/proxy/uid/prometheus/api/v1/query?query=up', auth)
        assert result['status'] == 'success' and result['data']['result'], 'Grafana Prometheus datasource has no up series'
    print('PASS existing Grafana database and authenticated Prometheus datasource query (read-only)', flush=True)


def main():
    # Retry the complete check so a lost port-forward is recreated.
    retry(check_netbox, 45)
    retry(check_grafana, 45)


if __name__ == '__main__':
    main()
