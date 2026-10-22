"""Synthetic NetBox bootstrap and lab-only Bifrost export (standard library)."""
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

FIXTURE = json.loads((Path(__file__).resolve().parent / 'fixture.json').read_text())
OWNER = FIXTURE['owner_tag']
PREFIX = FIXTURE['name_prefix']
SITE = FIXTURE['site']
MARKER = 'Synthetic fhs-netbox-lab bootstrap; no live endpoint'


class LabError(RuntimeError):
    pass


class API:
    def __init__(self, base, token):
        url = urllib.parse.urlsplit(base)
        if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port
                or url.path != '/netbox/' or url.query or url.fragment or url.username):
            raise LabError('Expected explicit loopback lab port-forward /netbox/ endpoint')
        if not token:
            raise LabError('Missing lab token')
        self.base, self.token = base, token
        self.root = base + 'api/'
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, path, method='GET', data=None):
        url = urllib.parse.urljoin(self.root, path)
        if not url.startswith(self.root):
            raise LabError('API pagination escaped lab endpoint')
        relative = urllib.parse.urlsplit(url).path.removeprefix(urllib.parse.urlsplit(self.root).path)
        category = {'dcim/devices': 'devices', 'dcim/interfaces': 'interfaces',
                    'ipam/ip-addresses': 'IP addresses'}.get('/'.join(relative.split('/')[:2]), 'other')
        context = method + ', ' + category
        request = urllib.request.Request(url, method=method,
            data=None if data is None else json.dumps(data).encode(),
            headers={'Authorization': 'Token ' + self.token, 'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=30) as response:
                return json.loads(response.read() or 'null')
        except urllib.error.HTTPError as error:
            error.close()
            raise LabError('Lab API request failed (' + context + ', HTTP ' + str(error.code) + ')') from None
        except TimeoutError:
            raise LabError('Lab API request timed out (' + context + ')') from None
        except urllib.error.URLError as error:
            reason = ('timeout' if isinstance(error.reason, TimeoutError) else
                      'connection refused' if isinstance(error.reason, ConnectionRefusedError) else
                      'connection unavailable')
            raise LabError('Lab API request failed (' + context + ', ' + reason + ')') from None
        except Exception:
            raise LabError('Lab API request failed (' + context + ')') from None

    def records(self, path, **filters):
        path += '?' + urllib.parse.urlencode({'limit': 100, **filters}, doseq=True)
        seen, rows = set(), []
        while path:
            if path in seen:
                raise LabError('Pagination cycle')
            seen.add(path)
            page = self.call(path)
            rows.extend(page['results'])
            path = page['next']
        ids = [row['id'] for row in rows]
        if len(ids) != len(set(ids)):
            raise LabError('Duplicate paginated records')
        return rows


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LabError('Unexpected lab API redirect')


def topology_fixture(directory):
    """Read the canonical dashboard contract; no alternate topology generator."""
    spec = importlib.util.spec_from_file_location('canonical_lab_topology', directory / 'topology.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = module.configured()
    if (data.get('synthetic') is not True or len(data['hosts']) != 132
            or len(data['switches']) != 51 or len(data['mesh_links']) != 648):
        raise LabError('Expected canonical 24 VCC / 27 FSP synthetic topology')
    return select_population(data)


def select_population(data):
    units = {f'VCCUnit{n}' for n in range(1, 5)} | {f'FSPUnit{n}' for n in range(1, 4)}
    import copy
    data = copy.deepcopy(data)
    selected = dict(data)
    for key in ('units', 'hosts', 'switches'):
        selected[key] = [r for r in data[key] if r.get('unit', r.get('name')) in units]
    switches = {r['name'] for r in selected['switches']}
    selected['mesh_links'] = [r for r in data.get('mesh_links', [])
                              if r['a_switch'] in switches and r['b_switch'] in switches]
    for switch in selected['switches']:
        switch['links'] = [r for r in switch['links']
                           if r.get('kind') != 'mesh' or r['neighbor']['name'] in switches]
    if (len(selected['hosts']), len(selected['switches']), len(selected['mesh_links'])) != (16, 7, 12):
        raise LabError('Expected reduced 16 FHS / 7 switches / 12 mesh links')
    return selected


def seed_offset(kind, source, fallback):
    if kind == 'fake':
        return 183 + source['number']
    match = re.fullmatch(r'(VCC|FSP)Unit([0-9]+)', source['unit'])
    if not match:
        raise LabError('Unknown canonical unit')
    role, number = match[1], int(match[2])
    if not 1 <= number <= (24 if role == 'VCC' else 27):
        raise LabError('Unknown canonical unit')
    if kind == 'switch':
        return 132 + (number if role == 'VCC' else 24 + number)
    host = re.search(r'-fhs([1-4])$', source['name'], re.I)
    if not host or (role == 'VCC' and host[1] != '1'):
        raise LabError('Unknown canonical host')
    return number if role == 'VCC' else 24 + (number - 1) * 4 + int(host[1])


def slug(value):
    return PREFIX + value.lower()


def ident(value):
    return value['id'] if isinstance(value, dict) else value


def tagged(row, tag):
    return tag in {item['slug'] for item in row.get('tags', [])}


class Bootstrap:
    """Create absent objects only. Never reconcile operator-owned facts."""
    def __init__(self, api):
        self.api = api
        self.created = {}
        self.new_ids = {}

    def ensure(self, endpoint, desired, key='slug', owned=None):
        current = self.api.records(endpoint)
        index = {}
        for row in current:
            identity = key(row) if callable(key) else row[key]
            if identity in index:
                raise LabError('Ambiguous bootstrap identity')
            index[identity] = row
        missing = []
        for row in desired:
            identity = key(row) if callable(key) else row[key]
            if identity in index:
                existing = index[identity]
                if owned and not owned(existing):
                    raise LabError('Bootstrap identity collides with unowned object')
            else:
                missing.append(row)
        new_ids = set()
        for start in range(0, len(missing), 100):
            result = self.api.call(endpoint, 'POST', missing[start:start + 100])
            for row in result:
                new_ids.add(row['id'])
                identity = key(row) if callable(key) else row[key]
                index[identity] = row
        self.created[endpoint] = len(missing)
        self.new_ids[endpoint] = new_ids
        return index


def seed(api, topology):
    b = Bootstrap(api)
    names = [OWNER, 'simulated-hardware', 'lab-logical', 'lab-provisioning', 'provisioning-interface']
    tags = b.ensure('extras/tags/', [{'name': name, 'slug': name,
        'description': MARKER} for name in names], owned=lambda row: row.get('description') == MARKER)
    tag = lambda name: tags[name]['id']
    owned = lambda row: tagged(row, OWNER)
    site = b.ensure('dcim/sites/', [{'name': SITE, 'slug': SITE, 'status': 'active',
        'tags': [tag(OWNER)], 'description': MARKER}], owned=owned)[SITE]
    manufacturer = b.ensure('dcim/manufacturers/', [{'name': PREFIX + 'synthetic',
        'slug': PREFIX + 'synthetic', 'description': MARKER}],
        owned=lambda row: row.get('description') == MARKER)[PREFIX + 'synthetic']
    types = b.ensure('dcim/device-types/', [{'model': PREFIX + kind, 'slug': PREFIX + kind,
        'manufacturer': manufacturer['id'], 'u_height': 1, 'description': MARKER}
        for kind in ['fhs', 'switch', 'fake']], owned=lambda row: row.get('description') == MARKER)
    roles = b.ensure('dcim/device-roles/', [{'name': PREFIX + kind, 'slug': PREFIX + kind,
        'color': '607d8b', 'description': MARKER} for kind in ['fhs', 'switch', 'provisioning']],
        owned=lambda row: row.get('description') == MARKER)
    b.ensure('extras/custom-fields/', [{'name': 'fhs_lab', 'label': 'FHS lab fixture', 'type': 'json',
        'object_types': ['dcim.device'], 'description': MARKER}], key='name',
        owned=lambda row: row.get('description') == MARKER)
    racks = b.ensure('dcim/racks/', [{'name': slug(unit['name']), 'site': site['id'],
        'status': 'active', 'u_height': 12, 'tags': [tag(OWNER)]} for unit in topology['units']],
        key='name', owned=lambda row: owned(row) and ident(row['site']) == site['id'])
    desired, sources = [], {}
    for kind, records in [('fhs', topology['hosts']), ('switch', topology['switches'])]:
        for record in records:
            name = slug(record['name'])
            sources[name] = (kind, record)
            desired.append({'name': name, 'device_type': types[PREFIX + kind]['id'],
                'role': roles[PREFIX + kind]['id'], 'site': site['id'],
                'rack': racks[slug(record['unit'])]['id'], 'status': 'active',
                'tags': [tag(OWNER), tag('simulated-hardware'), tag('lab-logical')],
                'custom_fields': {'fhs_lab': {'kind': 'logical', 'unit': record['unit'],
                    'canonical_name': record['name'], 'unit_type': record['role']}}})
    for number in range(1, FIXTURE['provisioning_count'] + 1):
        name = PREFIX + f'provision-{number:02d}'
        sources[name] = ('fake', {'management_ip': f'198.51.100.{number}', 'number': number})
        desired.append({'name': name, 'device_type': types[PREFIX + 'fake']['id'],
            'role': roles[PREFIX + 'provisioning']['id'], 'site': site['id'], 'status': 'active',
            'tags': [tag(OWNER), tag('simulated-hardware'), tag('lab-provisioning')],
            'custom_fields': {'fhs_lab': {'kind': 'provisioning',
                'uuid': str(uuid.uuid5(uuid.NAMESPACE_DNS, name)), 'driver': 'fake-hardware'}}})
    devices = b.ensure('dcim/devices/', desired, key='name',
        owned=lambda row: owned(row) and ident(row['site']) == site['id'])
    ports, addresses, primary = [], [], []
    for offset, (name, (kind, source)) in enumerate(sources.items(), 1):
        offset = seed_offset(kind, source, offset)
        device = devices[name]
        if kind == 'fhs':
            nics = [(p['node_device'], p['node_mac'], False) for p in source['interfaces']]
        elif kind == 'switch':
            nics = [(p['local_port'], None, False) for p in source['links']]
        else:
            nics = [('provision0', f'02:fa:00:00:00:{source["number"]:02x}', False)]
        if kind != 'fake':
            nics.insert(0, ('mgmt0', source['chassis_mac'], False))
        nics.append(('bmc0', f'02:fb:00:{offset >> 8:02x}:{offset & 255:02x}:00', True))
        for port_name, mac, management in nics:
            ports.append({'device': device['id'], 'name': port_name,
                'type': '1000base-t' if management or kind == 'fake' else '100gbase-x-qsfp28',
                'enabled': True, 'mgmt_only': management, 'tags': [tag(OWNER)] +
                ([tag('provisioning-interface')] if kind == 'fake' and not management else []),
                'description': MARKER})
        primary.append((name, source['management_ip'], f'203.0.113.{offset}', nics[0][0]))
    port_key = lambda row: (ident(row['device']), row['name'])
    interfaces = b.ensure('dcim/interfaces/', ports, key=port_key, owned=owned)
    macs = []
    for name, (kind, source) in sources.items():
        device = devices[name]
        entries = [(p['node_device'], p['node_mac']) for p in source.get('interfaces', [])]
        if kind == 'fake':
            entries = [('provision0', f'02:fa:00:00:00:{source["number"]:02x}')]
        if kind != 'fake':
            entries.append(('mgmt0', source['chassis_mac']))
        offset = seed_offset(kind, source, list(sources).index(name) + 1)
        entries.append(('bmc0', f'02:fb:00:{offset >> 8:02x}:{offset & 255:02x}:00'))
        for port_name, mac in entries:
            interface = interfaces[(device['id'], port_name)]
            macs.append({'mac_address': mac, 'assigned_object_type': 'dcim.interface',
                'assigned_object_id': interface['id'], 'description': MARKER,
                '_interface': interface})
    # Strip local bookkeeping before sending to NetBox.
    mac_index = b.ensure('dcim/mac-addresses/', [{k: v for k, v in row.items() if not k.startswith('_')}
        for row in macs], key=lambda row: row['mac_address'].lower(),
        owned=lambda row: row.get('description') == MARKER)
    for row in macs:
        interface = row['_interface']
        mac = mac_index[row['mac_address'].lower()]
        if ident(mac.get('assigned_object_id')) != interface['id']:
            raise LabError('Synthetic MAC assigned to unexpected interface')
        # Primary association is bootstrap-only, even when an operator clears it later.
        if interface['id'] in b.new_ids['dcim/interfaces/']:
            if interface.get('primary_mac_address') is None:
                api.call(f'dcim/interfaces/{interface["id"]}/', 'PATCH', {'primary_mac_address': mac['id']})
    for name, lan, oob, port_name in primary:
        device = devices[name]
        for address, interface_name in [(lan, port_name), (oob, 'bmc0')]:
            addresses.append({'address': address + '/32', 'status': 'active',
                'assigned_object_type': 'dcim.interface',
                'assigned_object_id': interfaces[(device['id'], interface_name)]['id'],
                'tags': [tag(OWNER)], 'description': MARKER})
    ips = b.ensure('ipam/ip-addresses/', addresses, key='address', owned=owned)
    for name, lan, oob, _ in primary:
        device = devices[name]
        # Fill primary pointers only on a newly created device.
        if device['id'] in b.new_ids['dcim/devices/']:
            api.call(f'dcim/devices/{device["id"]}/', 'PATCH',
                     {'primary_ip4': ips[lan + '/32']['id'], 'oob_ip': ips[oob + '/32']['id']})
    return {'created': b.created, 'logical': len(topology['hosts']) + len(topology['switches']),
            'provisioning': FIXTURE['provisioning_count'],
            'reachable': 0, 'policy': 'create missing objects; preserve existing facts'}


def export_nodes(api):
    devices = api.records('dcim/devices/', tag=[OWNER, 'lab-provisioning'], site=SITE, status='active')
    nodes, all_macs, identities = {}, set(), set()
    for device in devices:
        if (not tagged(device, OWNER) or not tagged(device, 'lab-provisioning')
                or not tagged(device, 'simulated-hardware')
                or device['status']['value'] != 'active' or device['site']['slug'] != SITE):
            raise LabError('Export selection includes an out-of-scope device')
        name = device['name']
        if not name.startswith(PREFIX) or name in nodes:
            raise LabError('Invalid or ambiguous lab name')
        fields = device.get('custom_fields', {}).get('fhs_lab')
        if not isinstance(fields, dict) or fields.get('kind') != 'provisioning' or fields.get('driver') != 'fake-hardware':
            raise LabError('Lab export requires explicit fake hardware properties')
        try:
            identity = str(uuid.UUID(fields['uuid']))
            lan = ipaddress.ip_interface(device['primary_ip4']['address']).ip
            oob = ipaddress.ip_interface(device['oob_ip']['address']).ip
            if lan not in ipaddress.ip_network('198.51.100.0/24') or oob not in ipaddress.ip_network('203.0.113.0/24'):
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise LabError('Missing or invalid lab identity/primary/OOB address') from None
        if identity in identities:
            raise LabError('Duplicate stable identity')
        identities.add(identity)
        ports = api.records('dcim/interfaces/', device_id=device['id'])
        selected = [p for p in ports if tagged(p, 'provisioning-interface')]
        if len(selected) != 1:
            raise LabError('Expected exactly one provisioning interface')
        port = selected[0]
        mac = (port.get('primary_mac_address') or {}).get('mac_address', '').lower()
        if (not tagged(port, OWNER) or port['mgmt_only'] or not port['enabled']
                or not re.fullmatch(r'02:fa:([0-9a-f]{2}:){3}[0-9a-f]{2}', mac) or mac in all_macs):
            raise LabError('Invalid or duplicate synthetic provisioning MAC')
        all_macs.add(mac)
        nodes[name] = {'name': name, 'uuid': identity, 'driver': 'fake-hardware',
            'driver_info': {}, 'nics': [{'mac': mac}], 'ipv4_address': str(lan),
            'host_groups': ['fhs_lab_provisioning'], 'properties': {'cpu_arch': 'x86_64'},
            'management_interface': 'fake', 'power_interface': 'fake',
            'boot_interface': 'fake', 'deploy_interface': 'fake',
            'inspect_interface': 'no-inspect', 'automated_clean': False}
    if not nodes:
        raise LabError('No active owned provisioning devices')
    return nodes


def private_export(api, destination):
    """Invalidate stale output first; replace only after complete validation."""
    destination = Path(destination)
    destination.unlink(missing_ok=True)
    temporary = None
    try:
        nodes = export_nodes(api)
        fd, temporary = tempfile.mkstemp(prefix='.lab-export-', dir=destination.parent)
        with os.fdopen(fd, 'w') as output:
            json.dump(nodes, output, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        return len(nodes)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
