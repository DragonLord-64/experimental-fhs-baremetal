#!/usr/bin/env python3
"""Supervisor-only read-only prerequisite check; output contains no credentials."""
import base64
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

from validate import request

K = ['minikube', '-p', 'fhs-test', 'kubectl', '--', '--context=fhs-test',
     '--request-timeout=30s', '-n', 'fhs-platform']


def main():
    report = {'journal_remote': next((str(p) for p in
              [Path('/usr/lib/systemd/systemd-journal-remote'), Path('/lib/systemd/systemd-journal-remote')]
              if p.is_file()), None), 'filebeat_in_path': shutil.which('filebeat')}
    secret = json.loads(subprocess.check_output(K + ['get', 'secret', 'elastic-credentials', '-o', 'json'], timeout=40))['data']
    report['publisher_secret_present'] = bool(secret.get('filebeat-password'))
    password = base64.b64decode(secret['elastic-password']).decode()
    process = subprocess.Popen(K + ['port-forward', '--address', '127.0.0.1',
                                     'service/elastic-elastic', ':9200'], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True)
    try:
        import selectors
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + 40
        url = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('owned forwarding exited')
            if not selector.select(timeout=1):
                continue
            line = process.stdout.readline().decode()
            match = re.search(r'Forwarding from 127.0.0.1:(\d+)', line)
            if match:
                url = 'http://127.0.0.1:' + match[1]
                break
        if url is None:
            raise TimeoutError('owned forwarding readiness')
        report['elasticsearch_version'] = request(url, 'elastic', password)['version']['number']
        for key, path in [('writer_role', '/_security/role/filebeat_writer'),
                          ('index_templates', '/_index_template/filebeat*'),
                          ('ilm_policies', '/_ilm/policy/filebeat*')]:
            try:
                result = request(url + path, 'elastic', password)
                if key == 'writer_role':
                    report[key] = result
                elif key == 'index_templates':
                    report[key] = [item['name'] for item in result.get('index_templates', [])]
                else:
                    report[key] = list(result)
            except Exception as error:
                report[key] = {'error_type': type(error).__name__}
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
        raise SystemExit(1)
