import importlib.util
import json
from pathlib import Path
import subprocess
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT/'platform/charts/fhs-platform'
spec = importlib.util.spec_from_file_location('home', CHART/'files/landing/server.py')
home = importlib.util.module_from_spec(spec); spec.loader.exec_module(home)


def render(prefix='', extra=()):
    p = subprocess.run(['helm', 'template', 'test', str(CHART),
                        '-n', 'fhs-discovery-portal-test', '--set-string', 'global.urlPrefix='+prefix,
                        *extra], capture_output=True, text=True, check=True)
    objects = list(yaml.safe_load_all(p.stdout))
    cm = next(o for o in objects if o and 'config.json' in o.get('data', {}))
    return json.loads(cm['data']['config.json']), objects


class LandingTest(unittest.TestCase):
    def test_generated_routes_and_disabled(self):
        for prefix in ('', '/hw', '/nested/hw/'):
            for host, scheme in [('one.example', 'http'), ('two.example', 'https')]:
                cfg, objects = render(prefix, ('--set-string', 'global.hostname='+host,
                                              '--set-string', 'global.scheme='+scheme))
                ingress = next(o for o in objects if o and o['kind']=='Ingress')
                self.assertEqual(host, ingress['spec']['rules'][0]['host'])
                paths = ingress['spec']['rules'][0]['http']['paths']
                self.assertEqual([p['path'] for p in paths[:3]], [s['url'] for s in cfg['services']])
                # Relative browser links inherit the current ingress host and scheme.
                self.assertTrue(all(s['url'].startswith(prefix.rstrip('/')+'/') for s in cfg['services']))
        cfg, objects = render('/hw', ('--set', 'netbox.enabled=false,grafana.enabled=false,logging.kibana.enabled=false,logging.filebeatSetup.enabled=false'))
        self.assertEqual([], cfg['services'])
        self.assertEqual(1, len(next(o for o in objects if o and o['kind']=='Ingress')['spec']['rules'][0]['http']['paths']))

    def test_markdown_custom_links_security(self):
        text = '# Operations\n**Daily** [Docs](https://docs.example/)\n<script>alert(1)</script>\n[X](javascript:alert)'
        cfg, _ = render('/hw', ('--set-string', 'landing.introduction='+text,
                               '--set-string', 'landing.links[0].name=Jira',
                               '--set-string', 'landing.links[0].url=https://jira.example/'))
        page = home.page(cfg).decode()
        self.assertIn('<h1>Operations</h1>', page)
        self.assertIn('<strong>Daily</strong>', page)
        self.assertIn('https://jira.example/', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('href="javascript:', page)
        self.assertNotIn('endpoint', page)
        for url in ('//evil', 'javascript:foo', 'https://u:p@example/', '/\\evil', 'http://[broken'):
            self.assertFalse(home.safe_url(url))

    def test_runtime_auth_failure_recovery_and_cache(self):
        state = {'code':302, 'calls':0, 'delay':0}
        class Endpoint(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                state['calls'] += 1
                time.sleep(state['delay'])
                self.send_response(state['code'])
                self.send_header('Location', 'http://must-not-follow.invalid/')
                self.end_headers()
        endpoint = ThreadingHTTPServer(('127.0.0.1', 0), Endpoint)
        thread = threading.Thread(target=endpoint.serve_forever, daemon=True); thread.start()
        service = {'id':'test', 'name':'Test', 'url':'/app/',
                   'endpoint':'http://127.0.0.1:'+str(endpoint.server_port), 'expected':[200,302,401,403]}
        poller = home.Poller([service], timeout=.05)
        cfg = {'prefix':'/hw', 'services':[service], 'links':[], 'introduction':'Hello'}
        web = ThreadingHTTPServer(('127.0.0.1',0), home.handler(cfg, poller))
        threading.Thread(target=web.serve_forever, daemon=True).start()
        base = 'http://127.0.0.1:'+str(web.server_port)
        try:
            self.assertEqual('not checked', poller.snapshot()['test']['status'])
            for code, expected in [(302,'reachable'),(401,'reachable'),(403,'reachable'),(500,'unavailable'),(200,'reachable')]:
                state['code']=code; poller.cycle()
                self.assertEqual(expected, poller.snapshot()['test']['status'])
            before=state['calls']
            for _ in range(12):
                for path in ('/hw/', '/hw/landing.js', '/hw/status.json'):
                    with urlopen(base+path) as response:
                        self.assertEqual(200,response.status)
                        self.assertIn("default-src 'none'",response.headers['Content-Security-Policy'])
            self.assertEqual(before,state['calls'])
            for path in ('/hw/status.json?url=http://evil','/app/config.json','/hw/server.py'):
                try:
                    urlopen(base+path)
                    self.fail('Private or arbitrary route accepted')
                except HTTPError as error:
                    self.assertEqual(404,error.code); error.close()
            with patch.object(home.time, 'time', return_value=time.time()+151):
                self.assertEqual('stale', poller.snapshot()['test']['status'])
            state['delay']=.15; poller.cycle()
            self.assertEqual('unavailable',poller.snapshot()['test']['status'])
            state['delay']=0; poller.cycle()
            self.assertEqual('reachable',poller.snapshot()['test']['status'])
            endpoint.shutdown(); endpoint.server_close(); poller.cycle()
            self.assertEqual('unavailable',poller.snapshot()['test']['status'])
            public=json.dumps(poller.snapshot())
            self.assertNotIn('127.0.0.1',public); self.assertNotIn('error',public)
        finally:
            web.shutdown(); web.server_close(); endpoint.server_close()

    def test_shared_polling_worker(self):
        poller=home.Poller([], interval=.02)
        with patch.object(poller,'cycle') as cycle:
            thread=threading.Thread(target=poller.run); thread.start()
            time.sleep(.07); poller.stop.set(); thread.join(1)
            self.assertGreaterEqual(cycle.call_count,2)
            self.assertLess(cycle.call_count,8)


class AcceptanceContractTest(unittest.TestCase):
    def test_rejects_foreign_scope_without_commands(self):
        spec = importlib.util.spec_from_file_location('landing_acceptance', Path(__file__).with_name('acceptance.py'))
        acceptance = importlib.util.module_from_spec(spec); spec.loader.exec_module(acceptance)
        for context, namespace in [('monitoring','fhs-discovery-portal-test'), ('fhs-test','production')]:
            with patch.object(acceptance.lab,'run') as command:
                with self.assertRaises(ValueError):
                    acceptance.lab.validate_scope(context, namespace)
                command.assert_not_called()

    def test_timeout_and_duplicate_probe_configuration_rejected(self):
        for extra in [('--set','landing.timeoutSeconds=0'), ('--set','landing.staleSeconds=30'),
                      ('--set-string','landing.extraChecks[0].id=netbox')]:
            with self.assertRaises(subprocess.CalledProcessError): render('/hw',extra)
