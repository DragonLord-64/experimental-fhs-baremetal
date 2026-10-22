#!/usr/bin/env python3
"""Supervisor-only real Filebeat replay/recovery check; never bootstraps or indexes documents."""
import argparse
import base64
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import time
import urllib.error
import urllib.request

from fixture import generate, verify


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('redirect rejected')


def request(url, username, password, payload=None):
    headers = {'Authorization': 'Basic ' + base64.b64encode(f'{username}:{password}'.encode()).decode()}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload is not None else None,
                                 headers=headers)
    with urllib.request.build_opener(NoRedirect).open(req, timeout=10) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--filebeat', type=Path, required=True)
    parser.add_argument('--credentials', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    # Do not put credentials in argv, logs, evidence, config or source control.
    mode = stat.S_IMODE(args.credentials.stat().st_mode)
    if mode & 0o077:
        raise ValueError('credentials must be private (mode 0600 or stricter)')
    private = json.loads(args.credentials.read_text())
    endpoint = private['elasticsearch_url'].rstrip('/')
    # Loopback forwarding only. No production/LAN endpoint, embedded auth or redirects.
    from urllib.parse import urlsplit
    parsed = urlsplit(endpoint)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.path:
        raise ValueError('requires bare loopback HTTP URL forwarded by supervisor')
    args.work.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(args.work, 0o700)
    source = generate(args.work, args.run, 0)
    config = Path(__file__).with_name('filebeat.yml').resolve()
    env = dict(os.environ, FHS_LOG_SOURCE=str(source.resolve()),
               FHS_ELASTICSEARCH_URL=endpoint, FHS_FILEBEAT_PASSWORD=private['filebeat_password'])
    command = [str(args.filebeat.resolve()), '-e', '--strict.perms=false', '-c', str(config),
               '--path.data', str((args.work / 'registry').resolve()),
               '--path.logs', str((args.work / 'logs').resolve())]
    version = subprocess.run([str(args.filebeat.resolve()), 'version'], capture_output=True, timeout=10, check=True)
    if b'filebeat version 9.5.5 ' not in version.stdout:
        raise ValueError('expected actual Filebeat 9.5.5')
    subprocess.run(command + ['test', 'config'], env=env, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=20, check=True)
    bad = dict(env, FHS_FILEBEAT_PASSWORD='invalid-synthetic-publisher-password')
    rejected = subprocess.run(command + ['test', 'output'], env=bad, capture_output=True, timeout=30)
    if rejected.returncode == 0 or b'401' not in rejected.stdout + rejected.stderr:
        raise ValueError('invalid publisher credentials did not clearly fail with HTTP 401')
    query = {'size': 20, 'track_total_hits': True, 'query': {'term': {'labels.test_run': args.run}}}

    def search():
        return request(endpoint + '/filebeat-fhs-one-9.5.5/_search',
                       private['reader_username'], private['reader_password'], query)

    def await_count(count):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Filebeat exited before delivery; inspect privately')
            try:
                result = search()
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                time.sleep(2)
                continue
            if result['hits']['total']['value'] >= count:
                verify(source, result, args.run, count)
                return result
            time.sleep(2)
        raise TimeoutError('Filebeat did not deliver exact fixture within 90 seconds')

    def start():
        return subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)

    def stop(process):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
                raise RuntimeError('Filebeat required forced stop')
        if process.returncode != 0:
            raise RuntimeError('Filebeat did not stop cleanly')

    try:
        previous = search()
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    else:
        if previous['hits']['total']['value'] != 0:
            raise ValueError('run already exists in Elasticsearch')
    process = start()
    try:
        first = await_count(3)
        (args.work / 'first-search.json').write_text(json.dumps(first))
        # Clean stop flushes registry; retain registry and original source on restart.
        stop(process)
        process = start()
        time.sleep(12)
        verify(source, search(), args.run, 3)
        generate(args.work, args.run, 1)
        final = await_count(6)
        (args.work / 'final-search.json').write_text(json.dumps(final))
    finally:
        stop(process)
    summary = {'real_filebeat_ingest_passed': True, 'one_host_exact_events_passed': True,
               'registry_restart_passed': True, 'invalid_auth_failed': True,
               'input': 'explicit-filestream-fallback', 'filebeat_version': '9.5.5',
               'events': 6, 'host': 'vccunit1-fhs1', 'run': args.run,
               'source_bytes': source.stat().st_size,
               'limitations': 'Clean restart only; at-least-once delivery, no crash/exactly-once guarantee. No journald/Ansible coverage.'}
    (args.work / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print request headers, credential content or response bodies.
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__,
                          'detail': 'Real logging validation failed; inspect private inputs and scoped resources.'}))
        raise SystemExit(1)
