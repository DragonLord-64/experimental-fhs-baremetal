#!/usr/bin/env python3
"""Export Ansible platform credentials and service URLs beside the Helm scripts."""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


def check_endpoints(endpoints):
    for key in ('netbox_url', 'pip_index_url', 'apt_cache_url', 'git_proxy_url', 'filebeat_elasticsearch_hosts'):
        urls = endpoints[key] if isinstance(endpoints[key], list) else [endpoints[key]]
        for url in urls:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError(f'Invalid credential-free URL for {key}')
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            socket.getaddrinfo(parsed.hostname, port)
            with socket.create_connection((parsed.hostname, port), timeout=10):
                pass
            if key not in ('apt_cache_url', 'git_proxy_url'):
                try:
                    # Do not send credentials; 401/403 confirms the HTTP service responds.
                    with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=15) as response:
                        if response.status not in (200, 204):
                            raise ValueError(f'Unexpected HTTP response for {key}')
                except urllib.error.HTTPError as error:
                    if error.code not in (401, 403, 405):
                        raise ValueError(f'HTTP {error.code} for {key}') from None
            print(f'Checked {key}: {parsed.hostname}:{port}')


def yaml_text(values):
    # JSON scalars are valid YAML and keep tokens/passwords safely quoted.
    lines = []
    for key, value in values.items():
        if isinstance(value, dict):
            lines.append(key + ':')
            lines.extend('  ' + line for line in yaml_text(value).splitlines())
        else:
            lines.append(f'{key}: {json.dumps(value)}')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--context', help='kubectl context; defaults to the currently selected context')
    parser.add_argument('--namespace', default='hw-management')
    parser.add_argument('--release', default='mid-cbf-hw')
    parser.add_argument('--output-directory', type=Path, default=Path(__file__).resolve().parent / 'platform-export')
    parser.add_argument('--check-endpoints', type=Path, metavar='FILE', help='check an exported file from this machine, without contacting Kubernetes')
    args = parser.parse_args()
    if args.check_endpoints:
        # Our generated YAML uses JSON scalar values, so no PyYAML is required.
        endpoints = {}
        for line in args.check_endpoints.read_text().splitlines():
            if not line.strip() or line.startswith('#'):
                continue
            key, value = line.split(':', 1)
            endpoints[key] = json.loads(value)
        check_endpoints(endpoints)
        return
    command = ['kubectl'] + (['--context', args.context] if args.context else []) + ['-n', args.namespace]

    def kube(*arguments, input_text=None):
        result = subprocess.run(command + list(arguments), input=input_text, capture_output=True, text=True)
        if result.returncode:
            # Never print Kubernetes responses that could contain credentials.
            raise RuntimeError('kubectl failed; check context, namespace, permissions and ready platform pods')
        return result.stdout

    services = json.loads(kube('get', 'services', '-o', 'json'))['items']
    services = {item['metadata']['name']: item for item in services}
    ingress = json.loads(kube('get', 'ingress', args.release + '-web', '-o', 'json'))
    netbox_routes = [(rule['host'], route['path'], route['backend']['service']['name'])
                     for rule in ingress['spec']['rules'] for route in rule['http']['paths']
                     if route['path'].rstrip('/').endswith('/netbox')]
    if len(netbox_routes) != 1:
        raise ValueError('Expected one NetBox route in the platform web ingress')
    hostname, prefix, netbox_service = netbox_routes[0]
    netbox_url = ('https' if ingress['spec'].get('tls') else 'http') + '://' + hostname + prefix.rstrip('/') + '/'

    def service_url(suffix, port):
        name = args.release + '-' + suffix
        service = services[name]
        if not any(p['port'] == port for p in service['spec']['ports']):
            raise ValueError(f'Unexpected port for {name}')
        return f'http://{name}.{args.namespace}.svc.cluster.local:{port}'

    endpoints = {'netbox_url': netbox_url,
                 'apt_cache_url': service_url('apt-cacher', 3142),
                 'pip_index_url': service_url('devpi', 3141) + '/root/pypi/+simple/',
                 'git_proxy_url': service_url('git-proxy', 3128),
                 'filebeat_elasticsearch_hosts': [service_url('elastic', 9200)]}
    check_endpoints(endpoints)
    secret = json.loads(kube('get', 'secret', 'fhs-platform-credentials', '-o', 'json'))['data']

    def value(key):
        result = base64.b64decode(secret[key]).decode().strip()
        if not result:
            raise ValueError('Missing required platform credential')
        return result

    token = value('api_token')
    # Use the chart's stable token, registering it in NetBox if needed. No rotation.
    code = '''from users.models import Token, User
import os
user = User.objects.get(username=os.environ.get('SUPERUSER_NAME', 'admin'))
token_value = TOKEN_VALUE
record = Token.objects.filter(version=1, plaintext=token_value).first()
if record is None:
    Token.objects.create(user=user, version=1, token=token_value, description='FHS Ansible platform', write_enabled=True)
elif record.user_id != user.pk or not record.enabled or not record.write_enabled or record.is_expired:
    raise RuntimeError('Existing platform token is unavailable; resolve separately')
print('FHS_PLATFORM_TOKEN_READY')
'''.replace('TOKEN_VALUE', repr(token))
    deployment = netbox_service  # The delivered chart uses the same fullname for both.
    result = kube('exec', '-i', 'deploy/' + deployment, '-c', 'netbox', '--',
                  '/opt/netbox/venv/bin/python', '/opt/netbox/netbox/manage.py', 'shell',
                  '--no-startup', '--no-imports', '--interface', 'python', input_text=code)
    if 'FHS_PLATFORM_TOKEN_READY' not in result:
        raise RuntimeError('NetBox did not confirm token registration')
    secrets = {'netbox_token': token,
               'filebeat_elasticsearch_username': 'filebeat_writer',
               'filebeat_elasticsearch_password': value('filebeat-password'),
               'filebeat_setup_credentials': {'filebeat_elasticsearch_username': 'elastic',
                                              'filebeat_elasticsearch_password': value('elastic-password')}}
    os.umask(0o077)
    args.output_directory.mkdir(parents=True, exist_ok=True)
    for name, data in [('platform-endpoints.yml', endpoints), ('platform-secrets.yml', secrets)]:
        path = args.output_directory / name
        # Do not follow an output symlink or leave a previously permissive file readable.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(yaml_text(data))
        print(f'Wrote {path}')
    print('Copy files to the Ansible host, then Vault-encrypt platform-secrets.yml. No files were copied automatically.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        # Exceptions from external APIs must not dump credential objects.
        print('Export/check failed: ' + (str(error) if isinstance(error, RuntimeError) else type(error).__name__) + '. Check the selected platform and service DNS/connectivity.', file=sys.stderr)
        sys.exit(1)
