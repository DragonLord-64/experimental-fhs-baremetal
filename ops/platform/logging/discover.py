#!/usr/bin/env python3
"""Supervisor-only owned Kibana view and real browser screenshot; no ES writes."""
import base64
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from preflight import K
from validate import NoRedirect


def main():
    from playwright.sync_api import sync_playwright
    secret = json.loads(subprocess.check_output(K + ['get', 'secret', 'elastic-credentials', '-o', 'json'], timeout=40))['data']
    password = base64.b64decode(secret['elastic-password']).decode()
    auth = 'Basic ' + base64.b64encode(('elastic:' + password).encode()).decode()
    process = subprocess.Popen(K + ['port-forward', '--address', '127.0.0.1',
                                     'service/elastic-elastic-kibana', ':5601'],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
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
        def api(path, body=None):
            req = urllib.request.Request(url + path, data=json.dumps(body).encode() if body is not None else None,
                  headers={'Authorization': auth, 'Content-Type': 'application/json', 'kbn-xsrf': 'fhs-logging'})
            with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
                return json.load(response)
        view_id = 'fhs-one-server-logs'
        try:
            current = api('/api/data_views/data_view/' + view_id)['data_view']
            assert current['title'] == 'filebeat-fhs-one-9.5.5' and current['timeFieldName'] == '@timestamp'
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            error.close()
            api('/api/data_views/data_view', {'data_view': {'id': view_id,
                'name': 'FHS one server logs', 'title': 'filebeat-fhs-one-9.5.5', 'timeFieldName': '@timestamp'}})
        run = 'logging-20261022-2'
        query = 'labels.test_run: "' + run + '" and host.name: "vccunit1-fhs1"'
        state = "(columns:!(host.name,log.level,message,event.id,service.name),dataSource:(dataViewId:'" + view_id + "',type:dataView),filters:!(),query:(language:kuery,query:'" + query + "'),sort:!(!('@timestamp',desc)))"
        global_state = '(filters:!(),refreshInterval:(pause:!t,value:60000),time:(from:now-24h,to:now))'
        destination = url + '/app/discover#/?' + urllib.parse.urlencode({'_g': global_state, '_a': state})
        output = Path('/tmp/fhs-logging-discover')
        output.mkdir(mode=0o700, exist_ok=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(viewport={'width': 1600, 'height': 1100},
                                              extra_http_headers={'Authorization': auth}, timezone_id='UTC')
                # Never send Basic credentials to a third-party origin.
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(url + '/') else route.abort())
                page = context.new_page()
                page.goto(destination, wait_until='domcontentloaded', timeout=90000)
                for text in ('vccunit1-fhs1', run + '-5', 'warning', 'error', 'info'):
                    page.get_by_text(text, exact=False).first.wait_for(timeout=90000)
                assert 'login' not in page.url.lower(), 'must show Discover, not login'
                page.screenshot(path=str(output / 'discover.png'), full_page=True)
                (output / 'result.json').write_text(json.dumps({'view': view_id, 'run': run,
                      'host': 'vccunit1-fhs1', 'screenshot': str(output / 'discover.png'),
                      'browser_visible_fields_passed': True, 'screenshot_inspected': False}, indent=2))
            finally:
                browser.close()
    finally:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    print('Owned Kibana data view and real Discover browser capture complete; screenshot needs visual inspection.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
        raise SystemExit(1)
