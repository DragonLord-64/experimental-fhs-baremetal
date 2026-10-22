#!/usr/bin/env python3
"""Reviewed VM operation: prepare isolated tools, scoped bootstrap, finite real ingest."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import tarfile
import time
import urllib.request

from preflight import K

ROOT = Path(__file__).resolve().parent
TOOLS = Path('/tmp/fhs-logging-tools')
PRIVATE = Path('/tmp/fhs-logging-private-20261022')


def main():
    # No Docker/ELK deployment, host packages, journal access or service changes.
    TOOLS.mkdir(exist_ok=True, mode=0o700)
    archive = TOOLS / 'filebeat-9.5.5-linux-x86_64.tar.gz'
    url = 'https://artifacts.elastic.co/downloads/beats/filebeat/' + archive.name
    if not archive.exists():
        with urllib.request.urlopen(url, timeout=60) as response, archive.open('xb') as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > 256 * 1024 * 1024:
                    raise ValueError('download size limit')
                output.write(chunk)
    with urllib.request.urlopen(url + '.sha512', timeout=30) as response:
        expected = response.read(4096).decode().split()[0]
    assert hashlib.file_digest(archive.open('rb'), 'sha512').hexdigest() == expected, 'archive checksum'
    binary = TOOLS / 'filebeat-9.5.5-linux-x86_64/filebeat'
    if not binary.exists():
        with tarfile.open(archive) as bundle:
            bundle.extractall(TOOLS, filter='data')
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    secret = json.loads(subprocess.check_output(K + ['get', 'secret', 'elastic-credentials', '-o', 'json'], timeout=40))['data']
    admin = base64.b64decode(secret['elastic-password']).decode()
    publisher = base64.b64decode(secret['filebeat-password']).decode()
    process = subprocess.Popen(K + ['port-forward', '--address', '127.0.0.1',
                                     'service/elastic-elastic', ':9200'], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True)
    try:
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + 40
        url = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('owned forwarding exited')
            if not selector.select(timeout=1):
                continue
            match = re.search(r'Forwarding from 127.0.0.1:(\d+)', process.stdout.readline().decode())
            if match:
                url = 'http://127.0.0.1:' + match[1]
                break
        if url is None:
            raise TimeoutError('forwarding readiness')
        credentials = PRIVATE / 'bootstrap.json'
        credentials.write_text(json.dumps({'elasticsearch_url': url, 'bootstrap_password': admin,
                                           'filebeat_password': publisher}))
        os.chmod(credentials, 0o600)
        subprocess.run(['python3', str(ROOT / 'bootstrap.py'), '--credentials', str(credentials)],
                       check=True, timeout=120)
        credentials.unlink()
        publisher_credentials = PRIVATE / 'publisher-reader.json'
        publisher_credentials.write_text(json.dumps({'elasticsearch_url': url, 'filebeat_password': publisher,
                         'reader_username': 'elastic', 'reader_password': admin}))
        os.chmod(publisher_credentials, 0o600)
        for batch in (1, 2):
            # Supervisor must run this reviewed operation under 1 CPU / 256 MiB budget.
            command = ['python3', str(ROOT / 'validate.py'), '--filebeat', str(binary),
                       '--credentials', str(publisher_credentials), '--work',
                       '/tmp/fhs-logging-check-' + str(batch), '--run', 'logging-20261022-' + str(batch)]
            subprocess.run(command, check=True, timeout=300)
        publisher_credentials.unlink()
    finally:
        for name in ('bootstrap.json', 'publisher-reader.json'):
            (PRIVATE / name).unlink(missing_ok=True)
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    print(json.dumps({'owned_reapply_passed': True, 'extra_elk_stacks': 0}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
        raise SystemExit(1)
