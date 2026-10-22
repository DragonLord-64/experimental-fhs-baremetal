"""Appended to an in-memory synthetic NODES assignment by the host wrapper.

Actual pinned Bifrost loader and isolated Ironic CRUD; no conductor, transitions,
DHCP/PXE, guest actions, physical addresses, or non-loopback API calls.
"""
import importlib.metadata
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

BINARY = '/var/lib/kolla/venv/bin/'
OWNER = 'fhs-netbox-lab'


def validate_nodes(nodes):
    if len(nodes) != 3:
        raise RuntimeError('Expected three fake provisioning nodes')
    macs = set()
    for name, node in nodes.items():
        if (not name.startswith('lab-nb-provision-') or node['driver'] != 'fake-hardware'
                or node['driver_info'] != {} or node['automated_clean'] is not False
                or node['host_groups'] != ['fhs_lab_provisioning']
                or ipaddress.ip_address(node['ipv4_address']) not in ipaddress.ip_network('198.51.100.0/24')):
            raise RuntimeError('Unexpected fake runtime input')
        for nic in node['nics']:
            if not nic['mac'].startswith('02:fa:') or nic['mac'] in macs:
                raise RuntimeError('Unexpected or duplicate fake MAC')
            macs.add(nic['mac'])
        for key in ['boot_interface', 'deploy_interface', 'management_interface', 'power_interface']:
            if node[key] != 'fake':
                raise RuntimeError('Fake interfaces are mandatory')


def loader(nodes):
    path = Path('/tmp/fhs-netbox-nodes.json')
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(nodes, output)
    env = {**os.environ, 'BIFROST_INVENTORY_SOURCE': str(path), 'OS_AUTH_TYPE': 'none',
           'DEFAULT_HOST_GROUPS': 'baremetal'}
    env.pop('BIFROST_NODE_NAMES', None)
    process = subprocess.run([BINARY + 'python', '/bifrost/playbooks/inventory/bifrost_inventory.py',
                              '--list'], env=env, capture_output=True, text=True, timeout=45)
    if process.returncode:
        raise RuntimeError('Actual pinned Bifrost inventory loader failed')
    result = json.loads(process.stdout)
    if (set(result['baremetal']['hosts']) != set(nodes)
            or set(result['fhs_lab_provisioning']['hosts']) != set(nodes)):
        raise RuntimeError('Actual Bifrost loader group mismatch')
    for name, node in nodes.items():
        actual = result['_meta']['hostvars'][name]
        for key in ['uuid', 'name', 'driver', 'driver_info', 'nics', 'ipv4_address']:
            if actual[key] != node[key]:
                raise RuntimeError('Actual Bifrost loader lost node identity/facts')
        if actual['provisioning_ipv4_address'] != node['ipv4_address']:
            raise RuntimeError('Actual Bifrost loader provisioning address mismatch')
    print(json.dumps({'actual_bifrost_loader': True, 'baremetal_count': len(nodes),
                      'provisioning_group_count': len(nodes)}), flush=True)


def api_call(path, method='GET', body=None):
    if (not path.startswith(('nodes', 'ports')) or method not in ['GET', 'POST', 'DELETE']
            or '/states' in path):
        raise RuntimeError('Forbidden fake API operation')
    request = urllib.request.Request('http://127.0.0.1:6385/v1/' + path,
        method=method, data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type': 'application/json', 'X-OpenStack-Ironic-API-Version': '1.82'})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read() or 'null')
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'Isolated Ironic {method} {path.split("/")[0]} HTTP {error.code}') from None


def enrollment(nodes):
    enabled = {entry.name for entry in importlib.metadata.entry_points(group='ironic.hardware.types')}
    if 'fake-hardware' not in enabled:
        raise RuntimeError('Pinned image lacks fake-hardware entrypoint')
    config = Path('/tmp/fhs-netbox-ironic.conf')
    config.write_text('[DEFAULT]\nauth_strategy=noauth\nenabled_hardware_types=fake-hardware\n'
        'enabled_boot_interfaces=fake\nenabled_deploy_interfaces=fake\n'
        'enabled_management_interfaces=fake\nenabled_power_interfaces=fake\n'
        'enabled_inspect_interfaces=no-inspect\nenabled_network_interfaces=noop\n'
        '[database]\nconnection=sqlite:////tmp/fhs-netbox-ironic.sqlite\n'
        '[api]\nhost_ip=127.0.0.1\nport=6385\napi_workers=1\n'
        '[oslo_concurrency]\nlock_path=/tmp\n')
    created, ports = [], []
    with open('/tmp/fhs-netbox-ironic.log', 'w') as log:
        subprocess.run([BINARY + 'ironic-dbsync', '--config-file', str(config), 'create_schema'],
                       stdout=log, stderr=log, check=True, timeout=45)
        api = subprocess.Popen([BINARY + 'ironic-api', '--config-file', str(config)],
                               stdout=log, stderr=log)
        try:
            for _ in range(60):
                if api.poll() is not None:
                    raise RuntimeError('Isolated Ironic API exited before readiness')
                try:
                    if api_call('nodes')['nodes'] != []:
                        raise RuntimeError('Disposable API must start empty')
                    break
                except OSError:
                    time.sleep(.5)
            else:
                raise RuntimeError('Isolated Ironic API readiness timed out')
            for name, source in nodes.items():
                body = {key: source[key] for key in ['name', 'uuid', 'driver', 'driver_info',
                    'properties', 'boot_interface', 'deploy_interface', 'management_interface',
                    'power_interface', 'inspect_interface', 'automated_clean']}
                body.update({'network_interface': 'noop', 'resource_class': OWNER,
                             'extra': {'owner': OWNER}})
                node = api_call('nodes', 'POST', body)
                created.append(node['uuid'])
                for nic in source['nics']:
                    port = api_call('ports', 'POST', {'node_uuid': node['uuid'],
                        'address': nic['mac'], 'pxe_enabled': False, 'extra': {'owner': OWNER}})
                    ports.append(port['uuid'])
                readback = api_call('nodes/' + node['uuid'])
                if (readback['driver'] != 'fake-hardware' or readback['uuid'] != source['uuid']
                        or readback['extra'].get('owner') != OWNER or readback['provision_state'] != 'enroll'):
                    raise RuntimeError('Fake enrollment readback mismatch')
                readports = api_call('ports?node=' + node['uuid'])['ports']
                if {p['address'] for p in readports} != {p['mac'] for p in source['nics']}:
                    raise RuntimeError('Fake enrollment MAC readback mismatch')
            print(json.dumps({'actual_ironic_enrolled_readback': len(created),
                              'provision_state': 'enroll', 'power_actions': 0}), flush=True)
        finally:
            try:
                for identity in reversed(ports):
                    port = api_call('ports/' + identity)
                    if port['extra'].get('owner') != OWNER:
                        raise RuntimeError('Refusing cleanup of unowned port')
                    api_call('ports/' + identity, 'DELETE')
                for identity in reversed(created):
                    node = api_call('nodes/' + identity)
                    if node['extra'].get('owner') != OWNER or node['driver'] != 'fake-hardware':
                        raise RuntimeError('Refusing cleanup of unowned node')
                    api_call('nodes/' + identity, 'DELETE')
                if api.poll() is None and api_call('nodes')['nodes']:
                    raise RuntimeError('Fake API cleanup left nodes')
                print(json.dumps({'owned_api_cleanup': True}), flush=True)
            finally:
                api.terminate()
                try:
                    api.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    api.kill()
                    api.wait()


try:
    validate_nodes(NODES)
    loader(NODES)
    enrollment(NODES)
except Exception as error:
    # Errors above contain fixed diagnostics and numeric HTTP status only.
    # Other exceptions (e.g. YAML/SDK errors) can include inputs: hide them.
    if type(error) is RuntimeError:
        raise SystemExit(str(error))
    raise SystemExit('Pinned Bifrost check failed; private runtime diagnostic suppressed')
