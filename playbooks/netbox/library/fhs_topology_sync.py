#!/usr/bin/python
"""Add unambiguous observed cables; never remove or move existing cables."""
from collections import defaultdict
import re
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.fhs_netbox import Sync, scalar


def mac(value):
    value = re.sub('[.:-]', '', str(value)).lower()
    return value if re.fullmatch('[0-9a-f]{12}', value) else ''


def synchronize(params, check):
    sync = Sync(params, check)
    observations = params['observations']; omitted = []; endpoints = {}; devices = {}
    for observation in observations:
        omitted.extend(observation['device'] + ': ' + item for item in observation.get('omissions', []))
    for observation in observations:
        name = observation['device']
        device = sync.find('dcim/devices/', name=name)
        if not device:
            omitted.append(name + ': device absent; import inventory first'); continue
        devices[name] = device
        for interface in sync.list('dcim/interfaces/', device_id=device['id']):
            endpoints[(name, interface['name'])] = interface
        if observation.get('family') == 'nexus':
            for port_name in set(observation.get('interfaces', [])):
                if (name, port_name) not in endpoints:
                    interface = sync.ensure('dcim/interfaces/', dict(device_id=device['id'], name=port_name),
                        dict(device=device['id'], name=port_name, type='other'), name + '/' + port_name)
                    endpoints[(name, port_name)] = interface
    def resolve(name, port):
        if name and name not in devices:
            device = sync.find('dcim/devices/', name=name)
            devices[name] = device
            if device:
                for interface in sync.list('dcim/interfaces/', device_id=device['id']):
                    endpoints[(name, interface['name'])] = interface
        if (name, port) in endpoints:
            return (name, port)
        matches = [key for key, interface in endpoints.items() if key[0] == name and mac(port) and
                   mac((interface.get('primary_mac_address') or {}).get('mac_address', interface.get('mac_address', ''))) == mac(port)]
        return matches[0] if len(matches) == 1 else None
    pairs = {}; serials = defaultdict(set)
    for observation in observations:
        name = observation['device']
        for neighbor in observation.get('neighbors', []):
            left = resolve(name, neighbor['local']); right = resolve(neighbor['remote'], neighbor['port'])
            if left and right and left != right:
                pairs[tuple(sorted((left, right)))] = 'LLDP'
            else:
                omitted.append(f'{name}/{neighbor["local"]}: unresolved LLDP neighbor {neighbor["remote"]}/{neighbor["port"]}')
        for item in observation.get('serials', []):
            serial = str(item.get('serial', '')).strip()
            if serial and serial.lower() not in ('unknown', 'n/a', 'none', '0'):
                serials[serial].add((name, item['port'], item['kind']))
    for serial, ends in serials.items():
        if len(ends) != 2 or not any(v[2] == 'nexus' for v in ends) or not any(v[2] in ('fpga', 'nic') for v in ends):
            omitted.append(serial + ': DAC serial needs exactly two distinct switch/host endpoints'); continue
        keys = [resolve(v[0], v[1]) for v in ends]
        if all(keys) and keys[0] != keys[1]:
            key = tuple(sorted(keys)); pairs[key] = 'DAC serial ' + serial
        else:
            omitted.append(serial + ': interface absent')
    peers = defaultdict(set)
    for left, right in pairs:
        peers[left].add(right); peers[right].add(left)
    # Validate all candidate pairs before creating interfaces/cables.
    valid = []
    for (left, right), evidence in sorted(pairs.items()):
        if len(peers[left]) > 1 or len(peers[right]) > 1:
            omitted.append(str((left, right)) + ': conflicting observations'); continue
        a, b = endpoints[left], endpoints[right]
        ac, bc = scalar(a.get('cable')), scalar(b.get('cable'))
        if ac or bc:
            if ac and ac == bc:
                cable = sync.request('GET', f'dcim/cables/{ac}/')
                terminations = cable.get('a_terminations', []) + cable.get('b_terminations', [])
                ids = {t.get('object_id') for t in terminations if t.get('object_type') == 'dcim.interface'}
                if ids == {a['id'], b['id']} and len(terminations) == 2:
                    continue
            omitted.append(str((left, right)) + ': existing cable preserved'); continue
        valid.append((a, b, evidence))
    for a, b, evidence in valid:
        data = dict(a_terminations=[dict(object_type='dcim.interface', object_id=a['id'])],
            b_terminations=[dict(object_type='dcim.interface', object_id=b['id'])], status='connected',
            description='FHS discovery: ' + evidence)
        sync.plan.append(dict(object='cable', action='create', before={}, after=data))
        if not sync.check:
            sync.request('POST', 'dcim/cables/', json=data)
    return dict(plan=sync.plan, omissions=omitted)


def main():
    module = AnsibleModule(argument_spec=dict(netbox_url=dict(required=True),
        netbox_token=dict(required=True, no_log=True), validate_certs=dict(type='bool', default=True),
        observations=dict(type='list', elements='dict', required=True), preview=dict(type='bool', default=False)), supports_check_mode=True)
    try:
        result = synchronize(module.params, module.check_mode or module.params['preview'])
        module.exit_json(changed=bool(result['plan']), **result)
    except Exception as error:
        module.fail_json(msg=str(error) if isinstance(error, ValueError) else 'Topology reconciliation failed; inspect NetBox state before retrying')


if __name__ == '__main__':
    main()
