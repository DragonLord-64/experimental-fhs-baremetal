#!/usr/bin/env python3
"""Synthetic discovery through delivered importer against the existing lab NetBox."""
import argparse
import importlib.util
import json
import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / 'scripts/hwmanage'))
    spec = importlib.util.spec_from_file_location('minimal', root / 'playbooks/netbox/ironic_minimal.py')
    minimal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(minimal)
    credentials = json.loads(Path(args.credentials).read_text())
    sync = minimal.Sync(dict(netbox_url=credentials['url'].replace('https://', 'http://'),
                             netbox_token=credentials['token'], validate_certs=True), False)
    prefix = 'SYN-HWM-' + uuid.uuid4().hex[:10]
    owned = []
    checks = []

    def create(path, data):
        row = sync.request('POST', path, json=data)
        owned.append((path, row['id']))
        return row

    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)
        print('PASS:', label, flush=True)

    try:
        site = create('dcim/sites/', dict(name=prefix, slug=prefix.lower()))
        maker = create('dcim/manufacturers/', dict(name=prefix, slug=prefix.lower()))
        dtype = create('dcim/device-types/', dict(model=prefix, slug=prefix.lower(), manufacturer=maker['id']))
        role = create('dcim/device-roles/', dict(name=prefix, slug=prefix.lower(), color='123456'))
        tag = create('extras/tags/', dict(name=prefix, slug=prefix.lower()))
        node_uuid = str(uuid.uuid4())
        node = dict(uuid=node_uuid, name=None, driver_info={})
        # Test-only RFC5737 BMC/host addresses and a locally administered MAC.
        record = dict(inventory=dict(system_vendor=dict(serial_number=prefix), bmc_address='192.0.2.237',
            boot=dict(pxe_interface='02:ba:00:00:ee:37'),
            interfaces=[dict(name='eno1', mac_address='02:ba:00:00:ee:37')]),
            plugin_data=dict(auto_discovered=True))
        fru = '\n'.join(['FRU Device Description : Builtin FRU Device (ID 0)',
            ' Product Manufacturer : Synthetic Vendor', ' Product Part Number : Synthetic Model',
            ' Product Serial : '+prefix])
        settings = dict(site=site['name'], role=role['slug'], device_type=dtype['model'])
        class Ironic:
            def inspection(self, selected):
                assert selected == node_uuid
                return record
            def ensure_name(self, selected, name, *, plan=False):
                assert selected['uuid'] == node_uuid and name == prefix
                return dict(selected, name=name)
        def run():
            return minimal.import_nodes({node_uuid: node}, Ironic(), settings, sync, probe=lambda *_: fru)[0]
        inventory_missing = False
        port_uuid = str(uuid.uuid4())
        node_updates = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_PATCH(self):
                if self.path.rstrip('/') != '/v1/nodes/'+node_uuid:
                    self.send_error(404)
                    return
                changes = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                for change in changes:
                    parts = change['path'].strip('/').split('/')
                    assert parts[0] != 'uuid'
                    target = node
                    for part in parts[:-1]:
                        target = target.setdefault(part, {})
                    target[parts[-1]] = change['value']
                node_updates.append(changes)
                body = json.dumps(dict(node, provision_state='enroll', maintenance=False)).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def do_GET(self):
                path = self.path.split('?')[0].rstrip('/')
                if path.endswith('/inventory'):
                    if inventory_missing:
                        self.send_error(404)
                        return
                    data = record
                elif path.endswith('/nodes') or path.endswith('/nodes/detail'):
                    from urllib.parse import parse_qs, urlsplit
                    query = parse_qs(urlsplit(self.path).query)
                    matched = 'name' not in query or query['name'] == [node.get('name')]
                    data = {'nodes': [dict(node, provision_state='enroll', maintenance=False)] if matched else []}
                elif path.endswith('/ports') or path.endswith('/ports/detail'):
                    from urllib.parse import parse_qs, urlsplit
                    query = parse_qs(urlsplit(self.path).query)
                    ports = [dict(uuid=port_uuid, node_uuid=node_uuid,
                                  address='02:ba:00:00:ee:37', pxe_enabled=True),
                             dict(uuid=str(uuid.UUID(int=1)), node_uuid=str(uuid.UUID(int=2)),
                                  address='02:ba:00:00:ee:38', pxe_enabled=True)]
                    if 'address' in query:
                        ports = [p for p in ports if p['address'] in query['address']]
                    if 'node' in query or 'node_uuid' in query:
                        owners = query.get('node', query.get('node_uuid'))
                        ports = [p for p in ports if p['node_uuid'] in owners]
                    if not path.endswith('/detail'):
                        ports = [{k: p[k] for k in ('uuid', 'address')} for p in ports]
                    data = {'ports': ports}
                elif path.endswith('/nodes/'+node_uuid):
                    data = dict(node, provision_state='enroll', maintenance=False)
                elif path in ('', '/v1'):
                    data = {'id': 'v1', 'version': '1.99', 'min_version': '1.1', 'status': 'CURRENT',
                            'links': [{'rel': 'self', 'href': 'http://127.0.0.1:'+str(self.server.server_port)+'/v1/'}]}
                    data = {'versions': [data]}
                else:
                    self.send_error(404)
                    return
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('X-OpenStack-Ironic-API-Minimum-Version', '1.1')
                self.send_header('X-OpenStack-Ironic-API-Maximum-Version', '1.99')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='hwmanage-entrypoint-') as folder:
                folder = Path(folder)
                def private(name, value):
                    path = folder/name
                    path.write_text(json.dumps(value))
                    path.chmod(0o600)
                    return str(path)
                secret = private('secrets.json', dict(netbox_token=credentials['token']))
                endpoint = private('endpoints.json', dict(netbox_url=sync.url[:-5]))

                bmc = private('bmc.json', dict(defaults=dict(ipmi_username='synthetic', ipmi_password='synthetic-only')))
                binary = folder/'ipmitool'
                binary.write_text('#!'+sys.executable+'\nprint('+repr(fru)+')\n')
                binary.chmod(0o700)
                from hwmanage_lib.settings import load
                config = load()[1]
                config['ironic']['endpoint'] = 'http://127.0.0.1:'+str(server.server_port)+'/v1'
                config['platform'].update(endpoints_file=endpoint, secrets_file=secret)
                config['credentials'].update(bmc_file=bmc, vault_password_file=None)
                config['import']['new_device_defaults'] = {k: settings[k] for k in ('site', 'role', 'device_type')}
                controller_config = private('controller.json', config)
                env = dict(os.environ, PATH=str(folder)+':'+str(Path(sys.executable).parent)+':'+os.environ['PATH'],
                    HWMANAGE_CONFIG_FILE=controller_config, ANSIBLE_CONFIG=str(root/'ansible.cfg'),
                    ANSIBLE_LOCAL_TEMP=str(folder/'ansible-tmp'))
                env.pop('OS_CLOUD', None)
                command = [str(Path(sys.executable).parent/'ansible-playbook'), '-i', 'localhost,',
                    str(root/'playbooks/netbox/ironic_import.yml'), '--start-at-task',
                    'Import saved inspection and verified remote FRU identity', '-e',
                    json.dumps(dict(hwmanage_selected_uuids=[node_uuid], hwmanage_config_file=controller_config))]
                preview = subprocess.run([*command, '--check'], env=env, capture_output=True, text=True, timeout=180)
                if preview.returncode:
                    print(preview.stdout)
                    raise AssertionError('Import preview failed')
                check(not node_updates and sync.find('dcim/devices/', serial=prefix) is None,
                      'Import plan writes neither NetBox device nor Ironic name')
                result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
                if result.returncode:
                    print(result.stdout)
                    raise AssertionError('Standalone import playbook failed; inspect synthetic fixture locally')
                sync.cache.clear()  # The standalone importer writes through a separate client.
                created = sync.find('dcim/devices/', serial=prefix)
                owned.append(('dcim/devices/', created['id']))
                created = sync.request('GET', f'dcim/devices/{created["id"]}/')
                owned.append(('ipam/ip-addresses/', created['oob_ip']['id']))
                check(True, 'Standalone Ansible import task uses immutable UUID selection, native SDK and controller FRU')
                check(node['name'] == prefix and len(node_updates) == 1,
                      'Initial import names the existing discovery with verified product serial')
                # Native inventory deliberately keeps a copied, plain endpoint.
                import yaml
                native_options = yaml.safe_load((root/'inventory/dev_env/netbox-inv.yml').read_text())
                native_options['api_endpoint'] = sync.url[:-5]
                native_source = private('netbox.yml', native_options)
                native_inventory = subprocess.run([str(Path(sys.executable).parent/'ansible-inventory'),
                    '-i', native_source, '--list', '-e', json.dumps(dict(hwmanage_config_file=controller_config))],
                    env=env, capture_output=True, text=True, timeout=180)
                if native_inventory.returncode or 'Failed to parse' in native_inventory.stderr:
                    descriptor, log = tempfile.mkstemp(prefix='hwmanage-inventory-', suffix='.log')
                    with os.fdopen(descriptor, 'w') as stream:
                        stream.write(native_inventory.stderr)
                    raise AssertionError('Native NetBox inventory failed; inspect private lab log')
                check('_meta' in json.loads(native_inventory.stdout),
                      'Direct native NetBox inventory uses copied endpoint and central credential path')
                wrapper = subprocess.run([sys.executable, str(root/'scripts/hwmanage/hwmanage'),
                    'inventory', 'import', '-i', 'ironic', '--all', '--plan'],
                    env=env, capture_output=True, text=True, timeout=180)
                if wrapper.returncode:
                    print(wrapper.stdout)
                    print(wrapper.stderr)
                    raise AssertionError('Wrapper import plan failed')
                check(True, 'Wrapper import plan runs native playbook with resolved UUID snapshot')
                from hwmanage_lib.settings import activated
                from hwmanage_lib.ironic import Ironic as NativeIronic
                with activated(controller_config):
                    client = NativeIronic()
                    # Simulate a discovery whose name has not yet been assigned.
                    node['name'] = None
                    previous_updates = len(node_updates)
                    host = dict(name=prefix+'-friendly', serial=prefix,
                                nics=[dict(mac='02:ba:00:00:ee:37')])
                    planned = client.reconcile(host, create=False, plan=True)
                    check(planned['uuid'] == node_uuid and len(node_updates) == previous_updates,
                          'Sync plan resolves unnamed discovery by MAC without writes or NetBox UUID')
                    renamed = client.reconcile(host, create=False)
                    check(renamed['uuid'] == node_uuid and renamed['name'] == prefix and len(node_updates) == previous_updates+1,
                          'Native SDK sync names the discovery without new registrations or ports')
                inventory_missing = True
                node['name'] = prefix+'-old-name'
                node.setdefault('driver_info', {})['redfish_address'] = 'https://192.0.2.237'
                previous_updates = len(node_updates)
                fallback = subprocess.run([sys.executable, str(root/'scripts/hwmanage/hwmanage'),
                    'inventory', 'import', '-i', 'ironic', '--all'],
                    env=env, capture_output=True, text=True, timeout=180)
                if fallback.returncode:
                    print(fallback.stdout)
                    print(fallback.stderr)
                    raise AssertionError('Minimal BMC/port fallback failed')
                check(node['name'] == prefix and len(node_updates) == previous_updates+1,
                      'Missing inventory fallback verifies BMC FRU and corrects the old Ironic name')
                sync.cache.clear()
                preserved = sync.find('dcim/devices/', serial=prefix)
                interfaces = sync.list('dcim/interfaces/', device_id=preserved['id'])
                check(preserved['id'] == created['id'] and {p['name'] for p in interfaces} == {'eno1', 'bmc'},
                      'Registered PXE fallback preserves existing NetBox interface name and device')
        finally:
            server.shutdown()
            server.server_close()
        first = sync.find('dcim/devices/', serial=prefix)
        check(first is not None, 'Standalone import persisted a device without hwmanage CLI')
        device = sync.request('GET', f'dcim/devices/{first["id"]}/')
        ports = sync.list('dcim/interfaces/', device_id=device['id'])
        check(device['serial'] == prefix and device['name'] == prefix, 'Unnamed Ironic discovery imported by verified FRU serial')
        check(not device.get('custom_fields', {}).get('ironic_uuid'), 'Import does not persist an Ironic UUID link')
        check(len(ports) == 2 and {p['name'] for p in ports} == {'eno1', 'bmc'}, 'Only provisioning and BMC interfaces imported')
        boot = next(p for p in ports if p['name'] == 'eno1')
        check(boot['primary_mac_address']['mac_address'].lower() == '02:ba:00:00:ee:37', 'Native NetBox primary MAC persisted')
        check(device['oob_ip']['address'] == '192.0.2.237/32' and not device['primary_ip4'], 'BMC assigned out-of-band; no Linux IP inferred')
        primary = create('ipam/ip-addresses/', dict(address='192.0.2.238/32', assigned_object_type='dcim.interface', assigned_object_id=boot['id']))
        approved = prefix+'-approved'
        sync.request('PATCH', f'dcim/devices/{device["id"]}/', json=dict(name=approved, primary_ip4=primary['id'], tags=[tag['id']], status='active'))
        again = run()
        actual = sync.request('GET', f'dcim/devices/{device["id"]}/')
        check(again['id'] == first['id'] and len(sync.list('dcim/devices/', serial=prefix)) == 1, 'Repeated discovery reuses one device')
        check(actual['name'] == approved and actual['primary_ip4']['id'] == primary['id'] and any(t['id'] == tag['id'] for t in actual['tags']) and actual['status']['value'] == 'active', 'Operator name, primary IP, tags and status preserved')
        before = len(sync.plan)
        bad = dict(minimal.observation(node, record, settings, lambda *_: fru), serial=prefix+'-other', name=approved)
        try:
            minimal.apply(sync, bad, settings)
        except ValueError:
            check(len(sync.plan) == before, 'Conflicting serial rejected before writes')
        else:
            raise AssertionError('Conflicting serial accepted')
    finally:
        cleanup_errors = []
        # Discover owned objects even if verification failed before recording IDs.
        sync.cache.clear()
        for remaining in sync.list('dcim/devices/', serial=prefix):
            for key in ('oob_ip', 'primary_ip4', 'primary_ip6'):
                ip = remaining.get(key)
                if ip and ('ipam/ip-addresses/', ip['id']) not in owned:
                    owned.append(('ipam/ip-addresses/', ip['id']))
            if ('dcim/devices/', remaining['id']) not in owned:
                owned.append(('dcim/devices/', remaining['id']))
        # Addresses first, then device; object cascade removes interfaces/MACs.
        priority = {'ipam/ip-addresses/': 0, 'dcim/devices/': 1, 'dcim/device-types/': 2,
                    'dcim/manufacturers/': 3}
        order = sorted(owned, key=lambda p: priority.get(p[0], 4))
        for path, identity in order:
            try:
                sync.request('DELETE', path+str(identity)+'/')
            except Exception as exc:
                cleanup_errors.append(path+str(identity)+': '+type(exc).__name__)
        Path(args.report).write_text(json.dumps(dict(checks=checks, cleanup_errors=cleanup_errors), indent=2)+'\n')
        if cleanup_errors:
            raise RuntimeError('Synthetic cleanup incomplete; inspect private report')


if __name__ == '__main__':
    main()
