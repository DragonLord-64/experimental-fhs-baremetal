#!/usr/bin/python
"""Native observed interfaces, module metadata and conflict-safe physical cables."""
from collections import defaultdict
import json
import re
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.fhs_netbox import Sync, scalar


def mac(value):
    value = re.sub('[.:-]', '', str(value)).lower()
    return value if re.fullmatch('[0-9a-f]{12}', value) else ''


def physical_port(name):
    return name.rsplit('/', 1)[0] if re.fullmatch(r'Ethernet\d+/\d+/\d+', name) else name


def metadata(sync, device, observation, endpoints, omitted):
    """Keep installed card interfaces and attach observed pluggable identity separately."""
    groups = defaultdict(list)
    for p in observation.get('ports', []): groups[p.get('connector', p['name'])].append(p)
    for connector, ports in groups.items():
        if len({(p.get('vendor', ''), p.get('part', ''), p.get('serial', '')) for p in ports if p.get('present') is not False}) > 1:
            omitted.append(observation['device']+'/'+connector+': inconsistent module identities across lanes'); continue
        for p in ports:
            key = (observation['device'], p['name']); interface = endpoints.get(key)
            if not interface: continue
            field_name = 'fhs_port_observation'
            field = sync.find('extras/custom-fields/', name=field_name)
            if field and scalar(field.get('type')) != 'json': raise ValueError('Incompatible '+field_name+' custom field')
            types = list((field or {}).get('object_types') or [])
            if 'dcim.interface' not in types: types.append('dcim.interface')
            sync.ensure('extras/custom-fields/', dict(name=field_name), dict(name=field_name, type='json', object_types=types), field_name)
            previous = (interface.get('custom_fields') or {}).get(field_name) or {}
            detail = dict(source=p.get('source', ''), physical_connector=connector,
                          reported=dict(previous.get('reported') or {}, **p.get('metadata', {})))
            if p.get('present') is not None: detail['present'] = p['present']
            elif 'present' in previous: detail['present'] = previous['present']
            endpoints[key] = sync.ensure('dcim/interfaces/', dict(id=interface['id']), dict(custom_fields={field_name: detail}), p['name']+' observation')
        populated = [p for p in ports if p.get('present') is not False]
        if not populated: continue  # No destructive inference of module removal.
        identities = {(p.get('vendor', ''), p.get('part', ''), p.get('serial', '')) for p in populated}
        if len(identities) != 1:
            omitted.append(observation['device']+'/'+connector+': inconsistent module identities across lanes'); continue
        vendor, part, serial = next(iter(identities))
        if not vendor or not part:
            omitted.append(observation['device']+'/'+connector+': incomplete module vendor/part; metadata not installed'); continue
        fields = {}; conflict = False
        for p in populated:
            for key, value in p.get('metadata', {}).items():
                if key == 'interface': continue
                if key in fields and fields[key] != value:
                    omitted.append(observation['device']+'/'+connector+': conflicting EEPROM metadata'); conflict = True; break
                fields[key] = value
        if conflict: continue
        description = json.dumps(dict(source=populated[0]['source'], physical_connector=connector,
                                      interfaces=[p['name'] for p in ports], reported=fields), sort_keys=True)
        # JSON field retains revision/date/cable_length and useful raw labels,
        # rather than coercing absent values or truncating a description.
        field_name = 'fhs_module_observation'
        old_field = sync.find('extras/custom-fields/', name=field_name)
        types = list((old_field or {}).get('object_types') or [])
        if old_field and scalar(old_field.get('type')) != 'json':
            raise ValueError('Incompatible fhs_module_observation custom field')
        for t in ('dcim.inventoryitem', 'dcim.module'):
            if t not in types: types.append(t)
        sync.ensure('extras/custom-fields/', dict(name=field_name), dict(name=field_name, type='json', object_types=types), field_name)
        detail = json.loads(description)
        if observation.get('family') == 'nexus':
            bay = sync.find('dcim/module-bays/', device_id=device['id'], name=connector)
            installed = sync.find('dcim/modules/', device_id=device['id'], module_bay_id=bay['id']) if bay else None
            if not installed or installed.get('serial', '') != serial:
                omitted.append(observation['device']+'/'+connector+': matching inventory module absent; import switch inventory first'); continue
            previous = (installed.get('custom_fields') or {}).get(field_name) or {}
            detail['reported'] = dict(previous.get('reported') or {}, **fields)
            sync.ensure('dcim/modules/', dict(id=installed['id']), dict(custom_fields={field_name: detail}), connector+' EEPROM')
            for p in ports:
                interface = endpoints.get((observation['device'], p['name']))
                if not interface: continue
                if scalar(interface.get('module')) not in (None, installed['id']):
                    omitted.append(observation['device']+'/'+p['name']+': existing interface module preserved'); continue
                updated = sync.ensure('dcim/interfaces/', dict(id=interface['id']), dict(module=installed['id']), p['name']+' connector association')
                endpoints[(observation['device'], p['name'])] = updated
        else:
            from ansible.module_utils.fhs_inventory_helpers import port_inventory
            port_inventory(sync, device, connector, vendor, part, serial, detail, endpoints.get((observation['device'], connector)))


def synchronize(params, check):
    sync = Sync(params, check)
    observations = params['observations']; omitted = []; diagnostics = []; endpoints = {}; devices = {}
    aliases = defaultdict(set); identities = defaultdict(set)
    for observation in observations:
        name = observation['device']
        omitted.extend(name+': '+v for v in observation.get('omissions', []))
        diagnostics.extend(dict(device=name, **v) for v in observation.get('diagnostics', []))
        device = sync.find('dcim/devices/', name=name)
        if not device:
            omitted.append(name+': device absent; import inventory first'); continue
        devices[name] = device; aliases[name].add(name)
        for alias in observation.get('identity', {}).get('aliases', []):
            if alias: aliases[str(alias)].add(name)
        for value in observation.get('identity', {}).get('macs', []):
            if mac(value): identities[mac(value)].add(name)
        for interface in sync.list('dcim/interfaces/', device_id=device['id']): endpoints[(name, interface['name'])] = interface
        # These are actual observations, not guessed peer hardware.
        for port_name in set(observation.get('interfaces', [])):
            if not port_name: continue
            if (name, port_name) not in endpoints:
                endpoints[(name, port_name)] = sync.ensure('dcim/interfaces/', dict(device_id=device['id'], name=port_name),
                    dict(device=device['id'], name=port_name, type='other'), name+'/'+port_name)
        metadata(sync, device, observation, endpoints, omitted)

    def device_name(name, chassis=''):
        matches = set(aliases.get(name, set()))
        if mac(chassis): matches |= identities.get(mac(chassis), set())
        exact = sync.find('dcim/devices/', name=name) if name else None
        if exact:
            devices[name] = exact; matches.add(name)
        return next(iter(matches)) if len(matches) == 1 else None

    def resolve(name, port, chassis='', remote=False):
        if len(aliases.get(name, set())) > 1: return None
        actual = device_name(name, chassis)
        if actual:
            device = devices[actual]
            if (actual, port) not in endpoints:
                for interface in sync.list('dcim/interfaces/', device_id=device['id']): endpoints[(actual, interface['name'])] = interface
            if (actual, port) in endpoints: return (actual, port)
            matches = [key for key, interface in endpoints.items() if key[0] == actual and mac(port) and
                mac((interface.get('primary_mac_address') or {}).get('mac_address', interface.get('mac_address', ''))) == mac(port)]
            if len(matches) == 1: return matches[0]
        # A dotted-MAC PortID can identify an existing peer outside selected scope.
        # Never fabricate a peer interface from a MAC that has no unique owner.
        if remote and mac(port):
            value = ':'.join(mac(port)[i:i+2] for i in range(0, 12, 2))
            matches = sync.list('dcim/mac-addresses/', mac_address=value)
            owners = [v.get('assigned_object') for v in matches if v.get('assigned_object_type') == 'dcim.interface' and v.get('assigned_object')]
            if len(owners) == 1:
                owner = owners[0]; peer = owner.get('device', {})
                if actual and peer.get('id') != devices[actual]['id']: return None
                if not actual and name and sync.find('dcim/devices/', name=name): return None
                key = (peer.get('name'), owner.get('name'))
                if all(key):
                    interface = sync.request('GET', 'dcim/interfaces/'+str(owner['id'])+'/')
                    endpoints[key] = interface; return key
        return None

    pairs = {}; serial_groups = defaultdict(list)
    def candidate(left, right, evidence):
        a, b = tuple(sorted(set(left))), tuple(sorted(set(right)))
        if not a or not b or set(a) & set(b): return
        signature = tuple(sorted((a, b)))
        pairs[signature] = evidence
        diagnostics.append(dict(candidate=[list(a), list(b)], evidence=evidence))
    for observation in observations:
        name = observation['device']
        for neighbor in observation.get('neighbors', []):
            left = resolve(name, neighbor['local']); right = resolve(neighbor.get('remote', ''), neighbor.get('port', ''), neighbor.get('chassis', ''), True)
            if left and right and left != right: candidate([left], [right], 'LLDP')
            else: omitted.append(f'{name}/{neighbor["local"]}: unresolved or unsupported LLDP peer {neighbor.get("remote", "")}/{neighbor.get("port", "")}')
        for item in observation.get('serials', []):
            serial = str(item.get('serial', '')).strip()
            if serial and serial.lower() not in ('unknown', 'n/a', 'none', '0'):
                serial_groups[serial].append(dict(item, device=name))

    def sides(records):
        groups = defaultdict(set)
        for item in records:
            key = (item['device'], physical_port(item['port']), item['kind'])
            groups[key].add((item['device'], item['port']))
        return groups
    consumed = set()
    def match_serial(records, evidence):
        groups = sides(records)
        if len(groups) != 2 or {k[2] for k in groups} != {'nexus', 'fpga'}: return False
        values = []
        for group in groups.values():
            resolved = [resolve(*key) for key in sorted(group)]
            if not all(resolved): return False
            values.append(resolved)
        candidate(*values, evidence); return True
    for serial, records in serial_groups.items():
        if match_serial(records, 'DAC exact serial '+serial): consumed.add(serial)
    # Explicit endpoint pairs retain precedence over the observed FS suffix rule.
    claimed = defaultdict(int)
    mappings = params.get('endpoint_pairs', [])
    for mapping in mappings:
        for field in ('host_serial', 'switch_serial'): claimed[mapping.get(field)] += 1
    for mapping in mappings:
        required = ('vendor', 'part', 'host_serial', 'switch_serial', 'evidence')
        if not all(isinstance(mapping.get(k), str) and mapping[k].strip() for k in required):
            omitted.append('DAC endpoint mapping requires vendor, part, both full serials and evidence'); continue
        a, b = mapping['host_serial'], mapping['switch_serial']
        if a in consumed or b in consumed or a == b or claimed[a] != 1 or claimed[b] != 1:
            omitted.append('DAC endpoint mapping conflicts with exact match or another mapping'); continue
        records = serial_groups.get(a, []) + serial_groups.get(b, [])
        if not records or any(r.get('vendor') != mapping['vendor'] or r.get('part') != mapping['part'] or
            r['serial'] != (a if r['kind'] == 'fpga' else b) for r in records):
            omitted.append('DAC endpoint mapping identity mismatch'); continue
        if match_serial(records, 'DAC verified endpoint pair '+a+' / '+b): consumed.update((a, b))
    # The hardware references show FS QDD-400G-PC01 ends labelled BASE-1/BASE-2.
    # Group every observation before considering a pair: a reused base, different
    # product, or an already claimed end must not silently select a cable.
    bases = defaultdict(list)
    for serial, records in serial_groups.items():
        match = re.fullmatch(r'(.+)-([12])', serial)
        if match:
            bases[match[1]].extend(records)
    for base, records in bases.items():
        serials = {r['serial'] for r in records}
        identities = {(str(r.get('vendor', '')).strip().upper(),
                       str(r.get('part', '')).strip().upper()) for r in records}
        if serials != {base+'-1', base+'-2'} or serials & consumed:
            continue
        if identities != {('FS', 'QDD-400G-PC01')}:
            continue
        groups = sides(records)
        if len(groups) != 2 or any(len({r['serial'] for r in records
                if (r['device'], physical_port(r['port']), r['kind']) == key}) != 1
                for key in groups):
            continue
        if match_serial(records, 'DAC FS paired ends '+base+'-1 / '+base+'-2'):
            consumed.update(serials)
    for serial in serial_groups.keys()-consumed:
        omitted.append(serial+': DAC needs exactly one observed FPGA connector and one switch connector; no unique supported serial pair; existing cables retained')
    peers = defaultdict(set)
    for signature in pairs:
        for side in signature:
            for endpoint in side: peers[endpoint].add(signature)
    for signature, evidence in sorted(pairs.items()):
        left, right = signature
        if any(len(peers[e]) > 1 for side in signature for e in side):
            omitted.append(str(signature)+': conflicting observations'); continue
        a = [endpoints[k] for k in left]; b = [endpoints[k] for k in right]
        existing = {scalar(i.get('cable')) for i in a+b if i.get('cable')}
        if existing:
            same = False
            if len(existing) == 1 and all(i.get('cable') for i in a+b):
                cid = next(iter(existing)); cable = sync.request('GET', f'dcim/cables/{cid}/')
                def ids(terms): return {t.get('object_id') for t in terms if t.get('object_type') == 'dcim.interface'}
                ca, cb = ids(cable.get('a_terminations', [])), ids(cable.get('b_terminations', []))
                expected = ({i['id'] for i in a}, {i['id'] for i in b})
                same = (ca, cb) == expected or (cb, ca) == expected
                same = same and len(cable.get('a_terminations', []))+len(cable.get('b_terminations', [])) == len(a)+len(b)
            if same: continue
            omitted.append(str(signature)+': existing cable preserved'); continue
        if any(i.get('mark_connected') for i in a+b):
            omitted.append(str(signature)+': occupied termination preserved'); continue
        data = dict(a_terminations=[dict(object_type='dcim.interface', object_id=i['id']) for i in a],
                    b_terminations=[dict(object_type='dcim.interface', object_id=i['id']) for i in b],
                    status='connected', description='FHS discovery: '+evidence)
        sync.plan.append(dict(object='cable', action='create', before={}, after=data))
        if not sync.check: sync.request('POST', 'dcim/cables/', json=data)
    return dict(plan=sync.plan, omissions=omitted, diagnostics=diagnostics)


def main():
    module = AnsibleModule(argument_spec=dict(netbox_url=dict(required=True), netbox_token=dict(required=True, no_log=True),
        validate_certs=dict(type='bool', default=True), observations=dict(type='list', elements='dict', required=True),
        endpoint_pairs=dict(type='list', elements='dict', default=[]), preview=dict(type='bool', default=False)), supports_check_mode=True)
    try:
        result = synchronize(module.params, module.check_mode or module.params['preview'])
        module.exit_json(changed=bool(result['plan']), **result)
    except Exception as error:
        module.fail_json(msg=str(error) if isinstance(error, ValueError) else 'Topology reconciliation failed; inspect private diagnostics and NetBox state')


if __name__ == '__main__': main()
