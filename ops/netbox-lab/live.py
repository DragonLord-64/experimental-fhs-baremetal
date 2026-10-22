#!/usr/bin/env python3
"""VM-only lab connection. Never print tokens, API bodies or subprocess errors."""
import base64
import contextlib
import json
import http.cookiejar
from html.parser import HTMLParser
import urllib.parse
import urllib.error
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from inventory import LabError

K = ['minikube', '-p', 'fhs-test', 'kubectl', '--', '--context=fhs-test',
     '-n', 'fhs-platform', '--request-timeout=20s']


@contextlib.contextmanager
def connection():
    secret = subprocess.check_output(K + ['get', 'secret', 'netbox-superuser', '-o', 'json'],
                                     stderr=subprocess.DEVNULL, timeout=30)
    token = base64.b64decode(json.loads(secret)['data']['api_token']).decode()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    proc = subprocess.Popen(K + ['port-forward', '--address=127.0.0.1', 'svc/netbox',
                                f'{port}:80'], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    try:
        from inventory import API
        api = API(f'http://127.0.0.1:{port}/netbox/', token)
        for _ in range(40):
            try:
                api.call('status/')
                break
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError('lab port-forward exited') from None
                time.sleep(1)
        else:
            raise RuntimeError('lab authenticated API readiness timed out')
        data = json.loads(secret)['data']
        api.ui_username = base64.b64decode(data['username']).decode()
        api.ui_password = base64.b64decode(data['password']).decode()
        yield api
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


class CSRFParser(HTMLParser):
    token = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'input' and attributes.get('name') == 'csrfmiddlewaretoken':
            self.token = attributes.get('value')


def ui_ready(api):
    from inventory import NoRedirect, LabError
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())
    login = api.base + 'login/'
    with opener.open(login, timeout=15) as response:
        parser = CSRFParser()
        parser.feed(response.read().decode())
    if not parser.token:
        raise LabError('Lab UI CSRF readiness failed')
    request = urllib.request.Request(login, data=urllib.parse.urlencode({
        'csrfmiddlewaretoken': parser.token, 'username': api.ui_username,
        'password': api.ui_password, 'next': '/netbox/dcim/devices/'}).encode(),
        headers={'Referer': login})
    # NoRedirect rejects success redirects before returning HTTPError. Handle a
    # same-origin redirect explicitly without ever forwarding a password.
    class LoginRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not newurl.startswith(api.base):
                raise LabError('Lab UI redirect escaped endpoint')
            return urllib.request.Request(newurl)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), LoginRedirect())
    with opener.open(request, timeout=15) as response:
        page = response.read().decode()
        if response.status != 200 or '/logout/' not in page or not any(c.name == 'sessionid' for c in jar):
            raise LabError('Authenticated lab UI readiness failed')
    # A permissioned endpoint establishes authenticated API access separately.
    api.records('users/tokens/')


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['probe', 'seed', 'verify', 'export', 'exercise'])
    parser.add_argument('--topology', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--ansible-inventory', default='ansible-inventory')
    args = parser.parse_args()
    if args.action == 'export':
        if args.output is None:
            parser.error('--output is required for export')
        # Invalidate before authentication/readiness as well as export validation.
        # A failed connection must never leave an older consumable inventory.
        args.output.unlink(missing_ok=True)
    with connection() as api:
        ui_ready(api)
        print(json.dumps({'authenticated_api': True, 'authenticated_ui': True}), flush=True)
        if args.action == 'exercise':
            from exercise import exercise
            print(json.dumps(exercise(api, args.ansible_inventory)), flush=True)
        if args.action == 'verify':
            from consumers import ansible_inventory, assert_inventory
            result = ansible_inventory(api, args.ansible_inventory)
            print(json.dumps({'actual_ansible_inventory': assert_inventory(api, result)}))
        if args.action == 'export':
            from inventory import private_export
            print(json.dumps({'exported': private_export(api, args.output)}))
        if args.action == 'seed':
            from inventory import seed, topology_fixture
            if args.topology is None:
                parser.error('--topology is required for seed')
            print(json.dumps(seed(api, topology_fixture(args.topology)), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except LabError as error:
        raise SystemExit(str(error))
    except Exception:
        raise SystemExit('Lab check failed; details suppressed to protect authentication and records')
