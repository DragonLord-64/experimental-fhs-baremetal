"""Supervisor-only temporary changes to one owned fake fixture; restore facts."""
import socket

from consumers import ansible_inventory, assert_inventory
from inventory import API, LabError, OWNER, PREFIX, export_nodes, ident, tagged


def exercise(api, binary):
    name = PREFIX + 'provision-01'
    selected = [row for row in api.records('dcim/devices/', name=name)
                if row['name'] == name and tagged(row, OWNER) and tagged(row, 'lab-provisioning')]
    if len(selected) != 1:
        raise LabError('Expected exactly one owned exercise fixture')
    device = selected[0]
    path = f'dcim/devices/{device["id"]}/'
    port = [p for p in api.records('dcim/interfaces/', device_id=device['id'])
            if tagged(p, OWNER) and tagged(p, 'provisioning-interface')]
    if len(port) != 1 or device['status']['value'] != 'active':
        raise LabError('Exercise fixture is not active with one owned provisioning interface')
    before = assert_inventory(api, ansible_inventory(api, binary))
    original_ip = ident(device['primary_ip4'])
    original_tags = [ident(t) for t in device['tags']]
    without_owner = [ident(t) for t in device['tags'] if t['slug'] != OWNER]
    if api.records('ipam/ip-addresses/', address='198.51.100.101/32'):
        raise LabError('Exercise address already exists; no reuse or overwrite')
    alternate = api.call('ipam/ip-addresses/', 'POST', {
        'address': '198.51.100.101/32', 'assigned_object_type': 'dcim.interface',
        'assigned_object_id': port[0]['id'], 'status': 'active',
        'tags': [t['id'] for t in device['tags'] if t['slug'] == OWNER],
        'description': 'Temporary fhs-netbox-lab source-of-truth exercise'})
    changed_ip = changed_status = changed_tags = False
    try:
        api.call(path, 'PATCH', {'primary_ip4': alternate['id']})
        changed_ip = True
        updated = ansible_inventory(api, binary)
        assert_inventory(api, updated)
        if updated['_meta']['hostvars'][name]['ansible_host'] != '198.51.100.101':
            raise LabError('Actual Ansible inventory did not reflect NetBox edit')
        if export_nodes(api)[name]['ipv4_address'] != '198.51.100.101':
            raise LabError('Bifrost export did not reflect NetBox edit')
        api.call(path, 'PATCH', {'primary_ip4': original_ip})
        changed_ip = False
        api.call(path, 'PATCH', {'status': 'offline'})
        changed_status = True
        offline = ansible_inventory(api, binary)
        assert_inventory(api, offline)
        if name in offline['_meta']['hostvars'] or name in export_nodes(api):
            raise LabError('Inactive fixture was included downstream')
        api.call(path, 'PATCH', {'status': 'active'})
        changed_status = False
        api.call(path, 'PATCH', {'tags': without_owner})
        changed_tags = True
        unowned = ansible_inventory(api, binary)
        assert_inventory(api, unowned)
        if name in unowned['_meta']['hostvars'] or name in export_nodes(api):
            raise LabError('Unowned fixture was included downstream')
        api.call(path, 'PATCH', {'tags': original_tags})
        changed_tags = False
        # A bound but non-listening socket guarantees an unavailable local endpoint.
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            broken = API(f'http://127.0.0.1:{sock.getsockname()[1]}/netbox/', api.token)
            try:
                ansible_inventory(broken, binary)
            except LabError:
                pass
            else:
                raise LabError('Unavailable endpoint silently reused inventory')
        for endpoint in ['', 'http://127.0.0.1/netbox/']:
            try:
                API(endpoint, api.token)
            except LabError:
                pass
            else:
                raise LabError('Missing/malformed endpoint was accepted')
    finally:
        current = api.call(path)
        # Do not clobber an unexpected concurrent operator edit during recovery.
        if changed_ip:
            if ident(current['primary_ip4']) != alternate['id']:
                raise LabError('Concurrent primary edit; explicit owned exercise recovery needed')
            api.call(path, 'PATCH', {'primary_ip4': original_ip})
        if changed_status:
            if current['status']['value'] != 'offline':
                raise LabError('Concurrent status edit; explicit owned exercise recovery needed')
            api.call(path, 'PATCH', {'status': 'active'})
        if changed_tags:
            if sorted(t['id'] for t in current['tags']) != sorted(without_owner):
                raise LabError('Concurrent tag edit; explicit owned exercise recovery needed')
            api.call(path, 'PATCH', {'tags': original_tags})
        candidate = api.call(f'ipam/ip-addresses/{alternate["id"]}/')
        if (not tagged(candidate, OWNER) or candidate['address'] != '198.51.100.101/32'
                or candidate['assigned_object_id'] != port[0]['id']):
            raise LabError('Temporary IP changed; explicit owned cleanup needed')
        api.call(f'ipam/ip-addresses/{alternate["id"]}/', 'DELETE')
    after = assert_inventory(api, ansible_inventory(api, binary))
    if after != before:
        raise LabError('Inventory counts not restored after exercise')
    return {'netbox_edit_reflected_in_actual_plugin_and_export': True,
            'inactive_and_unowned_excluded': True, 'unavailable_endpoint_failed': True,
            'missing_and_malformed_endpoint_failed': True, 'temporary_ip_removed': True,
            'original_facts_restored': True}
