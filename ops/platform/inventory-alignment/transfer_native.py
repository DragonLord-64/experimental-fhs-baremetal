#!/usr/bin/env python3
"""One disposable native transfer on an already-running delivered-chart NetBox.

Run inside its container with --vars pointing to protected playbook-style YAML.
Creates SYN-XFER-* objects only; retains them for review; never deletes.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--script', required=True)
    parser.add_argument('--vars', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('transfer', args.script)
    t = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t)
    api = t.API(*t.credentials(args.vars))
    prefix = 'SYN-XFER-'+uuid.uuid4().hex[:8]
    checks, owned = [], {}
    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)
    def create(path, **data):
        row = api.request('POST', path, json=data)
        owned.setdefault(path, []).append(row)
        return row
    site = create('dcim/sites/', name=prefix, slug=prefix.lower())
    maker = create('dcim/manufacturers/', name=prefix, slug=prefix.lower())
    role = create('dcim/device-roles/', name=prefix, slug=prefix.lower())
    dtype = create('dcim/device-types/', manufacturer=maker['id'], model=prefix, slug=prefix.lower(), u_height=1)
    cf = create('extras/custom-fields/', name=prefix.replace('-', '_'), type='json', object_types=['dcim.device'],
                label=prefix, description='Disposable transfer JSON metadata')
    devices = [create('dcim/devices/', name=prefix+'-'+name, site=site['id'], device_type=dtype['id'], role=role['id'],
                      comments='Synthetic transfer only', custom_fields={cf['name']: {'nested': {'id': 234, 'values': [1, None]}}})
               for name in ('switch', 'pdu-A', 'pdu-B', 'server')]
    switch, a, b, server = devices
    mgmt = create('dcim/interfaces/', device=switch['id'], name='mgmt0', type='1000base-t', mgmt_only=True)
    eth = create('dcim/interfaces/', device=server['id'], name='eth0', type='1000base-t')
    suffix = uuid.uuid4().hex[:8]
    address = '2001:db8:'+suffix[:4]+':'+suffix[4:]+'::1/64'
    ip = create('ipam/ip-addresses/', address=address, assigned_object_type='dcim.interface', assigned_object_id=mgmt['id'])
    mac = create('dcim/mac-addresses/', mac_address='02:fe:'+':'.join(suffix[i:i+2] for i in range(0,8,2)),
                 assigned_object_type='dcim.interface', assigned_object_id=mgmt['id'])
    api.request('PATCH', 'dcim/interfaces/'+str(mgmt['id'])+'/', json={'primary_mac_address': mac['id']})
    api.request('PATCH', 'dcim/devices/'+str(switch['id'])+'/', json={'primary_ip6': ip['id']})
    for pdu, name in ((a, 'PSU1'), (b, 'PSU2')):
        outlet = create('dcim/power-outlets/', device=pdu['id'], name='1', type='iec-60320-c13')
        port = create('dcim/power-ports/', device=server['id'], name=name, type='iec-60320-c14', maximum_draw=500)
        create('dcim/cables/', a_terminations=[dict(object_type='dcim.poweroutlet', object_id=outlet['id'])],
               b_terminations=[dict(object_type='dcim.powerport', object_id=port['id'])], label=prefix+'-'+name)
    create('dcim/cables/', a_terminations=[dict(object_type='dcim.interface', object_id=mgmt['id'])],
           b_terminations=[dict(object_type='dcim.interface', object_id=eth['id'])], label=prefix+'-uplink')
    # Fetch actual detail serializers and OPTIONS; export only owned disposable
    # objects. This isolates writes from the accepted hardware-import baseline.
    exporter = t.Exporter(api)
    for path, rows in owned.items():
        exporter.fields[path] = api.fields(path)
        exporter.raw[path] = {r['id']: api.request('GET', path+str(r['id'])+'/') for r in rows}
    records = []
    for path, rows in exporter.raw.items():
        for row in rows.values():
            # Other global custom fields have null defaults on these new objects.
            # Only this check's own definition/value is within its write scope.
            if 'custom_fields' in row:
                row['custom_fields'] = {cf['name']: row['custom_fields'][cf['name']]} if cf['name'] in row['custom_fields'] else {}
            data = {}
            for field, meta in exporter.fields[path].items():
                if meta.get('read_only') or field not in row or (path == 'dcim/interfaces/' and field == 'mac_address'):
                    continue
                try:
                    data[field] = exporter.encode(path, field, row[field], row)
                except t.TransferError as error:
                    exporter.issue(path, field, str(error))
            records.append(dict(path=path, key=exporter.identity(path, row),
                                ref=exporter.reference(path, row['id'])['$ref'], data=data))
    document = dict(format='fhs-netbox-inventory', version=1, source=api.request('GET', 'status/'),
                    records=records, issues=exporter.issues)
    # A second scope on the same disposable API stands in for the destination.
    # Natural keys change; source IDs are never emitted or reused. IP/MAC values
    # must also be distinct because both scopes coexist in this one database.
    serialized = json.dumps(document).replace(prefix, prefix+'-DST').replace(prefix.replace('-', '_'), (prefix+'-DST').replace('-', '_'))
    serialized = serialized.replace(prefix.lower(), (prefix+'-DST').lower())
    serialized = serialized.replace(address, address.replace('::1/', '::2/'))
    serialized = serialized.replace(mac['mac_address'], mac['mac_address'][:-2]+'ff' if mac['mac_address'][-2:].lower() != 'ff' else mac['mac_address'][:-2]+'fe')
    document = json.loads(serialized)
    t.private_json(str(args.report)+'.input.json', document)
    preview_api = t.API(*t.credentials(args.vars))
    preview = t.Importer(preview_api, True).run(document)
    check(preview['mapped'] == len(records), 'preview resolves all disposable objects')
    result = t.Importer(api).run(document)
    t.private_json(str(args.report)+'.partial', result)
    if result['issues']:
        print(json.dumps({'native_issues': result['issues']}))
    check(result['mapped'] == len(records), 'native import maps all disposable objects')
    check(not result['issues'], 'native supported fixture has no omitted writable fields')
    dest_switch = next(r for r in api.rows('dcim/devices/', fresh=True) if r['name'] == switch['name'].replace(prefix, prefix+'-DST'))
    check(dest_switch['id'] != switch['id'], 'destination device ID differs')
    dest_ip = api.request('GET', 'ipam/ip-addresses/'+str(t.scalar(dest_switch['primary_ip6']))+'/')
    check(dest_ip['id'] != ip['id'] and dest_ip['assigned_object_id'] != mgmt['id'], 'primary IP and interface use destination IDs')
    check(dest_switch['custom_fields'][(prefix+'-DST').replace('-', '_')]['nested']['id'] == 234, 'nested JSON custom-field value preserved literally')
    repeat = t.Importer(api).run(document)
    check(not repeat['actions'] and not repeat['issues'], 'native rerun has no updates or duplicates')
    cables = [r for r in api.rows('dcim/cables/', fresh=True) if r.get('label', '').startswith(prefix+'-DST')]
    check(len(cables) == 3, 'two PSU cables and one network cable persisted')
    check(api.request('GET', 'dcim/devices/'+str(switch['id'])+'/')['name'] == switch['name'], 'source record survives destination import')
    t.private_json(args.report, dict(prefix=prefix, checks=checks, source=document['source'], objects=len(records),
                                    issues=result['issues'], source_device_ids=[d['id'] for d in devices],
                                    destination_switch_id=dest_switch['id']))
    print(json.dumps(dict(checks=len(checks), objects=len(records), issues=result['issues'])))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print API payloads/credentials/response bodies.
        print('Native check failed: '+(str(error) if isinstance(error, AssertionError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
