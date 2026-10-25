"""Read-only topology observations. Serial strings remain exact, including suffixes."""
import json
import re


def port(value):
    return re.sub(r'^Eth(?=\d)', 'Ethernet', str(value or '').strip())


def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)


def topology_linux(name, lldp, eeprom, fpga):
    result = dict(device=name, family='linux', interfaces=[], neighbors=[], serials=[], omissions=[])
    if lldp.get('rc', 1) == 0:
        try:
            body = json.loads(lldp.get('stdout', '{}'))
            entries = body.get('lldp', {}).get('interface', [])
            if isinstance(entries, dict):
                entries = [entries]
            for entry in entries:
                for local, neighbor in entry.items():
                    for data in neighbor if isinstance(neighbor, list) else [neighbor]:
                        chassis = data.get('chassis', {})
                        for remote, details in chassis.items():
                            if not isinstance(details, dict) or remote in ('id', 'descr', 'mgmt-ip', 'capability'):
                                continue
                            pid = data.get('port', {}).get('id', {})
                            result['neighbors'].append(dict(local=local, remote=remote,
                                port=port(pid.get('value')), subtype=pid.get('type', 'ifname')))
        except (ValueError, TypeError, AttributeError):
            result['omissions'].append('Unrecognized lldpcli JSON')
    else:
        result['omissions'].append('LLDP unavailable; no daemon or device configuration changed')
    for probe in eeprom:
        if probe.get('rc', 1):
            result['omissions'].append('Cable EEPROM probe failed: ' + str(probe.get('item', {})))
            continue
        raw = probe.get('stdout', '')
        serial = re.search(r'(?im)^\s*Vendor [Ss][Nn]\s*:\s*(\S+)', raw)
        if serial and re.search(r'(?i)copper|passive|active cable|DAC|CR4|CR8', raw):
            result['serials'].append(dict(port=probe['item']['interface'], serial=serial[1], kind='nic'))
    for probe in fpga:
        if probe.get('rc', 1):
            result['omissions'].append('Cable EEPROM probe failed: ' + str(probe.get('item', {})))
            continue
        index = probe['item']['card_index']
        for match in re.finditer(r'(?ms)^\s*QSFP(\d+):\s*\n(.*?)(?=^\s*QSFP\d+:|\Z)', probe.get('stdout', '')):
            serial = re.search(r'vendor_serial_number\s*:\s*(\S+)', match[2])
            if serial:
                result['serials'].append(dict(port=f'C{index}-QSFP{match[1]}', serial=serial[1], kind='fpga'))
    return result


def topology_nexus(name, lldp, optics):
    result = dict(device=name, family='nexus', interfaces=[], neighbors=[], serials=[], omissions=[])
    for observation, kind in ((lldp, 'lldp'), (optics, 'optics')):
        try:
            body = json.loads(observation) if isinstance(observation, str) else observation
            for row in objects(body):
                if kind == 'lldp' and row.get('l_port_id'):
                    result['interfaces'].append(port(row['l_port_id']))
                    result['neighbors'].append(dict(local=port(row['l_port_id']),
                        remote=row.get('sys_name') or row.get('chassis_id', ''),
                        port=port(row.get('port_id')), subtype='auto'))
                if kind == 'optics' and row.get('interface'):
                    local = port(row['interface'])
                    result['interfaces'].append(local)
                    serial = row.get('serialnum') or row.get('vendor_serial_no')
                    # Only identified copper cables qualify; never pair optical transceivers.
                    if serial and re.search(r'(?i)DAC|copper|twinax|\bCR\d*\b|CU\d', ' '.join(str(row.get(k, '')) for k in ('type', 'partnum', 'cisco_product_id'))):
                        result['serials'].append(dict(port=local, serial=str(serial).strip(), kind='nexus'))
        except (ValueError, TypeError):
            result['omissions'].append('Unrecognized Nexus ' + kind + ' JSON')
    return result


class FilterModule:
    def filters(self):
        return dict(fhs_topology_linux=topology_linux, fhs_topology_nexus=topology_nexus)
