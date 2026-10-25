"""Small installation home; one fixed-destination polling worker, no external dependencies."""
import html
import json
import re
import threading
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


def safe_url(value):
    try:
        u = urlsplit(value)
    except ValueError:
        return False
    return bool((u.scheme in ('http', 'https') and u.hostname and not u.username and not u.password)
                or (value.startswith('/') and not value.startswith('//'))) and not any(c in value for c in '\r\n\\')


def markdown(text):
    # Deliberately small Markdown subset. Escape HTML before adding our own tags.
    def inline(line):
        escaped = html.escape(line)
        def link(m):
            url = html.unescape(m[2])
            return '<a href="'+html.escape(url, quote=True)+'">'+m[1]+'</a>' if safe_url(url) else m[1]
        escaped = re.sub(r'\[([^\]]+)\]\(([^\s)]+)\)', link, escaped)
        return re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', escaped)
    lines = []
    for line in text.splitlines():
        heading = re.match(r'^(#{1,3}) (.*)', line)
        if heading:
            n = len(heading[1]); lines.append(f'<h{n}>'+inline(heading[2])+f'</h{n}>')
        elif line.strip():
            lines.append('<p>'+inline(line)+'</p>')
    return '\n'.join(lines)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Poller:
    def __init__(self, services, timeout=4, interval=60, stale=150):
        self.services = services
        self.timeout, self.interval, self.stale = timeout, interval, stale
        self.lock = threading.Lock()
        self.results = {}
        self.stop = threading.Event()
        self.opener = build_opener(NoRedirect(), ProxyHandler({}))

    def check(self, service):
        try:
            try:
                with self.opener.open(service['endpoint'], timeout=self.timeout) as response:
                    code = response.status
            except HTTPError as error:
                code = error.code
                error.close()
            available = code in service['expected']
        except Exception:
            available = False
        with self.lock:
            self.results[service['id']] = (available, time.time())

    def cycle(self):
        # At most eight deployment-configured destinations; a slow application
        # must not delay checks of the others or stretch the 60-second cycle.
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(self.check, self.services))

    def run(self):
        while not self.stop.is_set():
            start = time.monotonic()
            self.cycle()
            self.stop.wait(max(0, self.interval-(time.monotonic()-start)))

    def snapshot(self):
        with self.lock:
            results = dict(self.results)
        now = time.time()
        return {s['id']: {'status': ('not checked' if s['id'] not in results else
                 'stale' if now-results[s['id']][1] > self.stale else
                 'reachable' if results[s['id']][0] else 'unavailable'),
                 'checked': datetime.fromtimestamp(results[s['id']][1], timezone.utc).isoformat()
                 if s['id'] in results else None} for s in self.services}


def page(config):
    esc = html.escape
    cards = ''.join('<article><h2><a href="'+esc(s['url'], quote=True)+'">'+esc(s['name'])+
                    '</a></h2><p data-service="'+esc(s['id'], quote=True)+'">not checked</p></article>'
                    for s in config['services'] if safe_url(s['url']))
    links = ''.join('<li><a href="'+esc(s['url'], quote=True)+'">'+esc(s['name'])+'</a></li>'
                    for s in config['links'] if safe_url(s['url']))
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>HW management</title><style>'
            'body{font:1rem system-ui;max-width:64rem;margin:auto;padding:2rem;line-height:1.6}'
            'nav{display:flex;flex-wrap:wrap;gap:1rem}article{border:1px solid;padding:1rem;border-radius:.5rem}'
            'a:focus-visible{outline:3px solid;outline-offset:.3rem}</style></head><body><main>'
            '<h1>HW management</h1>'+markdown(config['introduction'])+
            '<p>Availability is reachability from this checker, not complete functional health. '
            'Applications retain their own sign-in.</p><nav aria-label="Hardware applications">'+cards+
            '</nav><ul>'+links+'</ul></main><script src="'+esc(config['prefix'], quote=True)+'/landing.js" defer></script></body></html>').encode()


SCRIPT = b'''async function refresh(){try{const r=await fetch('./status.json',{cache:'no-store'});if(!r.ok)throw new Error('status cache unreachable');const s=await r.json();document.querySelectorAll('[data-service]').forEach(e=>{const v=s[e.dataset.service];e.textContent=v.status+(v.checked?' - last checked '+v.checked:'');});}catch{document.querySelectorAll('[data-service]').forEach(e=>e.textContent='stale - status cache unreachable');}}refresh();setInterval(refresh,15000);'''


def handler(config, poller):
    body = page(config)
    prefix = config['prefix']
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if prefix and self.path == prefix:
                self.send_response(302); self.send_header('Location', prefix+'/'); self.end_headers(); return
            routes = {prefix+'/': ('text/html; charset=utf-8', body),
                      prefix+'/landing.js': ('text/javascript', SCRIPT),
                      prefix+'/status.json': ('application/json', json.dumps(poller.snapshot()).encode()),
                      '/healthz': ('text/plain', b'ok')}
            if self.path not in routes:
                self.send_error(404); return
            content_type, data = routes[self.path]
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(data)
    return Handler


if __name__ == '__main__':
    config = json.loads(Path('/app/config.json').read_text())
    poller = Poller(config['services'], timeout=config['timeout'], stale=config['stale'])
    threading.Thread(target=poller.run, daemon=True).start()
    from http.server import HTTPServer
    HTTPServer(('0.0.0.0', 8080), handler(config, poller)).serve_forever()
