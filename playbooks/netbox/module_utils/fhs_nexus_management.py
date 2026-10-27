"""Conservative NX-OS management interface text observation and reconciliation."""
import ipaddress
import re


def observe(output):
    result = dict(interface='', addresses=[], diagnostics=[])
    try:
        if not isinstance(output, str) or re.search(r'(?im)^\s*(?:%\s*)?(?:invalid|error\b|not supported|ambiguous|incomplete)', output):
            raise ValueError('Management command failed or unsupported')
        names = re.findall(r'(?m)^\s*(mgmt\d+) is (?:up|down|administratively down)\b', output)
        if len(names) != 1:
            raise ValueError('Expected one observed management interface')
        result['interface'] = names[0]
        # NX-OS show interface mgmt0 reports an explicit prefix on this line.
        values = re.findall(r'(?im)^\s*(?:Internet Address is|Internet address is|IPv6 address(?: is)?[: ]+)\s*(\S+)', output)
        addresses = []
        for value in values:
            if '/' not in value:
                raise ValueError('Management address has no observed prefix')
            address = ipaddress.ip_interface(value.rstrip(','))
            if address.ip.is_unspecified or address.ip.is_multicast or address.ip.is_loopback:
                raise ValueError('Management address is not usable')
            if address.ip.is_link_local:
                continue
            addresses.append(str(address))
        addresses = sorted(set(addresses))
        if any(sum(ipaddress.ip_interface(a).version == v for a in addresses) > 1 for v in (4, 6)):
            raise ValueError('Multiple management addresses in one family; primary selection ambiguous')
        if not addresses:
            raise ValueError('No usable prefixed management address observed')
        result['addresses'] = addresses
    except ValueError as error:
        result['addresses'] = []
        result['diagnostics'].append(str(error)+'; existing addresses and primary selection preserved')
    return result


def reconcile(sync, device, observation, include_ips):
    diagnostics = list(observation.get('diagnostics', []))
    name = observation.get('interface', '')
    if not device or not name:
        return diagnostics+['Management reconciliation deferred: existing parent or interface observation missing']
    did = device['id']
    interface = sync.find('dcim/interfaces/', device_id=did, name=name)
    addresses = observation.get('addresses', []) if include_ips else []
    existing = []
    # Preflight all addresses before any writes, including the interface.
    for value in addresses:
        ip = ipaddress.ip_interface(value)
        matches = sync.list('ipam/ip-addresses/', address=str(ip.ip))
        if len(matches) > 1:
            return diagnostics+['Ambiguous management address ownership; existing state preserved']
        old = matches[0] if matches else None
        if old and (old.get('vrf') is not None or old.get('assigned_object_type') not in (None, 'dcim.interface') or
                    old.get('assigned_object_id') not in (None, (interface or {}).get('id'))):
            return diagnostics+['Conflicting management address ownership; existing state preserved']
        existing.append((value, old, ip.version))
    if include_ips and not addresses:
        return diagnostics
    data = dict(device=did, name=name, mgmt_only=True)
    if not interface:
        data['type'] = 'other'  # Do not infer connector/speed from an interface name.
    interface = sync.ensure('dcim/interfaces/', dict(device_id=did, name=name), data, name)
    for value, old, version in existing:
        key = dict(id=old['id']) if old else dict(address=value)
        address = sync.ensure('ipam/ip-addresses/', key, dict(address=value, assigned_object_type='dcim.interface',
                              assigned_object_id=interface['id']), name+' address')
        sync.ensure('dcim/devices/', dict(id=did), {'primary_ip'+str(version): address['id']}, 'management primary IP')
    return diagnostics
