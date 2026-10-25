"""Read-only observations. Missing reports never assert absent hardware."""
import json
import re

# FS product data sheet: QDD-400G-PC01 is passive copper, despite SDK techstr.
# Exact identities, not a substring heuristic; optical serials never pair fiber.
DAC_PARTS = {('FS', 'QDD-400G-PC01'), ('FS', 'QDD-400G-2QPC01')}


def port(value):
    return re.sub(r'^Eth(?=\d)', 'Ethernet', str(value or '').strip())


def connector(value):
    value = port(value)
    return value.rsplit('/', 1)[0] if re.fullmatch(r'Ethernet\d+/\d+/\d+', value) else value


def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)


def dac(vendor, part_number):
    return (str(vendor).strip().upper(), str(part_number).strip().upper()) in DAC_PARTS


def qsfp_ports(probes):
    """Keep every observed port, including Removed, and every reported field."""
    ports = []; omissions = []; diagnostics = []
    for probe in probes:
        index = probe.get('item', {}).get('card_index')
        label = 'card ' + str(index)
        diagnostics.append(dict(probe='bw_qsfp_info', source=label, rc=probe.get('rc'),
                                state='failed' if probe.get('rc', 1) else 'discovered'))
        if probe.get('rc', 1):
            omissions.append(label + ': QSFP probe failed; ports/modules preserved'); continue
        matches = list(re.finditer(r'(?m)^\s*QSFP(\d+):[ \t]*$', probe.get('stdout', '')))
        if not matches:
            omissions.append(label + ': no QSFP headings parsed; no fixed port count assumed')
        for pos, match in enumerate(matches):
            raw = probe['stdout'][match.end():matches[pos+1].start() if pos+1 < len(matches) else len(probe['stdout'])]
            fields = {}
            for key, value in re.findall(r'^\s*([^:\n]+?)\s*:[ \t]*(.*?)\s*$', raw, re.M):
                if key in fields and fields[key] != value:
                    raise ValueError(label + ': conflicting QSFP field ' + key)
                fields[key] = value
            name = f'C{index}-QSFP{match[1]}'
            presence = fields.get('Present', '').lower()
            present = False if presence in ('removed', 'absent', 'not present') else True if presence == 'present' else None
            # A clipped photo/report may have identity without its presence line.
            # Identity is retained; an absent module cannot be inferred from clipping.
            record = dict(name=name, card_index=index, connector=name, metadata=fields, present=present,
                          vendor=fields.get('vendor_name', ''), part=fields.get('vendor_partnumber', ''),
                          serial=fields.get('vendor_serial_number', ''), revision=fields.get('vendor_rev', ''),
                          source='bw_qsfp_info USB display')
            record['dac'] = present is not False and dac(record['vendor'], record['part'])
            ports.append(record)
            diagnostics.append(dict(probe='QSFP port', port=name, present=present, vendor=record['vendor'],
                                    part=record['part'], serial=record['serial'], fields=list(fields)))
            if present is not False and not record['dac']:
                omissions.append(name + ': module identity is not a supported verified DAC; use LLDP for fiber')
    if len({p['name'] for p in ports}) != len(ports):
        raise ValueError('Duplicate QSFP port reports')
    return dict(ports=ports, omissions=omissions, diagnostics=diagnostics)


def topology_linux(name, lldp, eeprom, fpga, identity=None):
    result = dict(device=name, family='linux', interfaces=[], neighbors=[], serials=[], omissions=[],
                  identity=identity or {}, diagnostics=[])
    if lldp.get('rc', 1) == 0:
        try:
            body = json.loads(lldp.get('stdout', '{}'))
            entries = body.get('lldp', {}).get('interface', [])
            if isinstance(entries, dict): entries = [entries]
            if not isinstance(entries, list): raise ValueError('interface shape')
            for entry in entries:
                for local, neighbor in entry.items():
                    for data in neighbor if isinstance(neighbor, list) else [neighbor]:
                        chassis = data.get('chassis', {})
                        for remote, details in chassis.items():
                            if not isinstance(details, dict) or remote in ('id', 'descr', 'mgmt-ip', 'capability'): continue
                            pid = data.get('port', {}).get('id', {})
                            if not pid.get('value'):
                                result['omissions'].append(local + ': LLDP missing PortID'); continue
                            result['interfaces'].append(local)
                            result['neighbors'].append(dict(local=local, remote=remote, port=port(pid['value']),
                                subtype=pid.get('type', 'ifname'), chassis=details.get('id', {}).get('value', ''),
                                management_ip=details.get('mgmt-ip', ''), source='lldpcli JSON'))
        except (ValueError, TypeError, AttributeError):
            result['omissions'].append('Unrecognized lldpcli JSON')
    else:
        result['omissions'].append('LLDP unavailable; no daemon or device configuration changed')
    if lldp.get('rc', 1) == 0 and not result['neighbors'] and not result['omissions']:
        result['omissions'].append('LLDP returned no neighbors; existing connections preserved')
    result['diagnostics'].append(dict(probe='lldpcli', rc=lldp.get('rc'), parsed_neighbors=len(result['neighbors'])))
    # Ordinary NIC connections, including copper, use LLDP. EEPROM is metadata,
    # not an alternate inference of the fiber or ordinary network cable.
    for probe in eeprom:
        if probe.get('rc', 1):
            result['omissions'].append('Cable EEPROM probe failed: ' + str(probe.get('item', {})))
    nic_ports = []
    for probe in eeprom:
        if probe.get('rc',1): continue
        fields = dict(re.findall(r'^\s*([^:\n]+?)\s*:[ \t]*(.*?)\s*$',probe.get('stdout',''),re.M))
        vendor = fields.get('Vendor name',''); part_number = fields.get('Vendor PN',''); serial = fields.get('Vendor SN','')
        local = probe.get('item',{}).get('interface')
        if local and (vendor or part_number or serial):
            nic_ports.append(dict(name=local,connector=local,vendor=vendor,part=part_number,serial=serial,
                present=True,metadata=fields,source='ethtool module EEPROM',dac=False))
    parsed = qsfp_ports(fpga)
    result.update(ports=nic_ports + parsed['ports'])
    result['omissions'].extend(parsed['omissions']); result['diagnostics'].extend(parsed['diagnostics'])
    for p in parsed['ports']:
        result['interfaces'].append(p['name'])
        if p['dac'] and p['serial']:
            result['serials'].append(dict(port=p['name'], serial=p['serial'], kind='fpga',
                                         vendor=p['vendor'], part=p['part'], connector=p['connector']))
    return result


def topology_nexus(name, lldp, optics):
    result = dict(device=name, family='nexus', interfaces=[], neighbors=[], serials=[], ports=[], omissions=[], diagnostics=[])
    for observation, kind in ((lldp, 'lldp'), (optics, 'optics')):
        try:
            body = json.loads(observation) if isinstance(observation, str) else observation
            if not isinstance(body, (dict, list)): raise ValueError('JSON object required')
            count = 0
            for row in objects(body):
                local = row.get('l_port_id') or row.get('local_port')
                if kind == 'lldp' and local:
                    result['interfaces'].append(port(local))
                    result['neighbors'].append(dict(local=port(local), remote=row.get('sys_name') or row.get('chassis_id', ''),
                        port=port(row.get('port_id')), subtype='auto', chassis=row.get('chassis_id', ''), source='NX-OS LLDP JSON'))
                    count += 1
                if kind == 'optics' and row.get('interface'):
                    local = port(row['interface']); result['interfaces'].append(local)
                    fields = {k: v for k, v in row.items() if not isinstance(v, (dict, list))}
                    vendor = row.get('name') or row.get('vendor_name', '')
                    part_number = row.get('partnum') or row.get('vendor_part_no') or row.get('cisco_product_id', '')
                    serial = row.get('serialnum') or row.get('vendor_serial_no', '')
                    status = str(row.get('sfp') or row.get('qsfp') or row.get('qsfp_or_cfp', '')).lower()
                    present = False if status in ('not present', 'absent', 'not applicable') else True if status in ('present', 'inserted') else None
                    p = dict(name=local, connector=connector(local), vendor=vendor, part=part_number, serial=str(serial).strip(),
                             present=present, metadata=fields, source='NX-OS transceiver JSON', dac=present is not False and dac(vendor, part_number))
                    result['ports'].append(p); count += 1
                    if p['dac'] and p['serial']:
                        result['serials'].append(dict(port=local, serial=p['serial'], kind='nexus', vendor=vendor,
                                                     part=part_number, connector=p['connector']))
            result['diagnostics'].append(dict(probe='NX-OS '+kind, parsed_rows=count))
            if not count: result['omissions'].append('NX-OS '+kind+': empty or unsupported report; existing records preserved')
        except (ValueError, TypeError):
            result['omissions'].append('Unrecognized Nexus ' + kind + ' JSON')
    result['interfaces'] = list(dict.fromkeys(result['interfaces']))
    return result


def observed_modules(records, probes, interface_type):
    parsed = qsfp_ports(probes)
    return [dict(r, interfaces=[dict(name=p['name'], type=interface_type) for p in parsed['ports']
                                if p['card_index'] == r.get('card_index', r.get('index'))]) for r in records]


def pluggable_items(observation):
    return [dict(name=p.get('connector',p['name'])+' transceiver',kind='QSFP',
                 serial=p['serial'],part=p['part'],model=p['part'],manufacturer=p.get('vendor') or 'NA')
            for p in observation.get('ports',[]) if p.get('present') is not False and p.get('serial') and p.get('part')]


class FilterModule:
    def filters(self):
        return dict(fhs_topology_linux=topology_linux, fhs_topology_nexus=topology_nexus,
                    fhs_qsfp_ports=qsfp_ports, fhs_observed_fpga_ports=observed_modules, fhs_pluggable_items=pluggable_items)
