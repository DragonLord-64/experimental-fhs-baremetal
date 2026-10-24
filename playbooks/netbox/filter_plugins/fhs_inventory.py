"""Normalize observed FHS output; do not infer PCI association from product names."""
import re
from ansible.errors import AnsibleFilterError


def first(text, pattern):
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else ''


def cards(text, index_pattern, serial_pattern, part_pattern, version_pattern, firmware_pattern, pci_map):
    headings = list(re.finditer(serial_pattern, text, re.MULTILINE))
    indices = list(re.finditer(index_pattern, text, re.MULTILINE))
    # Count raw SDK index labels too: a malformed index must not disappear just
    # because the configured numeric pattern could not recognize it.
    index_labels = list(re.finditer(r'^\s*Index\s*:', text, re.MULTILINE))
    if len(indices) != len(headings) or len(index_labels) > len(indices):
        raise AnsibleFilterError('Incomplete FPGA inventory; every Index record needs one recognized serial and index')
    result = []
    for pos, heading in enumerate(headings):
        block = text[heading.start():headings[pos + 1].start() if pos + 1 < len(headings) else len(text)]
        if len(list(re.finditer(index_pattern, block, re.MULTILINE))) != 1:
            raise AnsibleFilterError('Incomplete FPGA inventory; every serial needs exactly one Index record')
        index = first(block, index_pattern)
        part = first(block, part_pattern)
        firmware = first(block, firmware_pattern)
        missing = [name for name, valid in [('Index', index.isdigit()), ('Part Number', bool(part)), ('BMC Version', bool(firmware))] if not valid]
        if missing:
            raise AnsibleFilterError('Incomplete FPGA card record '+str(pos + 1)+'; missing or unmatched fields: '+', '.join(missing)+'; check configured output patterns')
        endpoints = pci_map.get(index, pci_map.get(int(index), []))
        for endpoint in endpoints:
            if not re.fullmatch(r'[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]', endpoint.get('address', '')):
                raise AnsibleFilterError('Invalid explicit FPGA PCI address')
        result.append(dict(name='CARD '+index, serial=heading.group(1).strip(), card_index=int(index),
                           part=part, version=first(block, version_pattern), bmc_firmware=firmware,
                           pci_endpoints=endpoints))
    if len({c['card_index'] for c in result}) != len(result):
        raise AnsibleFilterError('Duplicate FPGA card index')
    warnings = ['SDK reports repeated serials for distinct card indices; preserving reported values and using module bays for identity'] if len({c['serial'] for c in result}) != len(result) else []
    return {'cards': result, 'warnings': warnings, 'complete': not warnings}


def modules(records, interface_type):
    result = []
    for record in records:
        index = record.get('card_index', record.get('index'))
        if index is None or not str(index).isdigit():
            raise AnsibleFilterError('Every FPGA needs its actual card_index')
        if not record.get('part') or not record.get('serial'):
            raise AnsibleFilterError('FPGA module needs a discovered part and serial')
        result.append(dict(record, bay='FPGA CARD '+str(index), position=str(index),
                           interfaces=[dict(name=f'C{index}-QSFP{port}', type=interface_type) for port in range(3)]))
    if len({r['bay'] for r in result}) != len(result):
        raise AnsibleFilterError('FPGA module bays collide')
    return result


def vpd(components, probes):
    observations = {p['nic_item']['name']:p.get('stdout','') for p in probes if not p.get('skipped') and p.get('rc',0)==0}
    result=[]
    for component in components:
        item=dict(component)
        raw=observations.get(item['name'],'')
        for key, pattern in [('part',r'\[PN\]\s+Part number:\s*(\S+)'),('serial',r'\[SN\]\s+Serial number:\s*(\S+)')]:
            value=first(raw,pattern)
            if value:item[key]=value
        result.append(item)
    return result

def nic_candidates(candidates, vf_probes, name_probes):
    import base64
    virtual={p['item']['interface'] for p in vf_probes if p.get('stat',{}).get('exists')}
    names={p['item']['interface']:base64.b64decode(p.get('content','')).decode('utf-8',errors='replace').strip() for p in name_probes}
    return [dict(p,physical_port_name=names.get(p['interface'],'')) for p in candidates
            if p['interface'] not in virtual and not re.match(r'^(?:p\d+)?(?:pf\d+)?(?:vf|sf)\d+',names.get(p['interface'],''))]


def nic_cards(ports, driver_probes, link_probes, identity_probes, drivers, part_pattern, serial_pattern):
    def observations(probes,key):
        return {p['item'][key]:p.get('stdout','') for p in probes if not p.get('skipped') and p.get('rc',1)==0}
    driver_texts=observations(driver_probes,'interface')
    links=observations(link_probes,'interface')
    identities=observations(identity_probes,'address')
    groups={};warnings=[]
    missing={'','unknown','none','n/a','unavailable','not','not_specified','000000','00000000'}
    for port in ports:
        interface=port['interface'];address=port['address'].lower();text=driver_texts.get(interface,'')
        values={key:value.strip() for key,value in re.findall(r'^([^:\n]+):[ \t]*(.*)$',text,re.MULTILINE)}
        driver=values.get('driver','')
        if not driver or drivers and driver not in drivers:
            warnings.append(interface+': driver unavailable or outside selected NIC drivers; existing data preserved');continue
        if values.get('bus-info','').lower()!=address:
            warnings.append(interface+': ethtool PCI address does not match host facts; not imported');continue
        identity=identities.get(address,'');part=first(identity,part_pattern);serial=first(identity,serial_pattern)
        if part.lower() in missing or serial.lower() in missing:
            warnings.append(interface+': physical card part/serial unavailable from VPD; no physical grouping invented');continue
        group=groups.setdefault((part,serial),dict(part=part,serial=serial,interfaces=[],functions=[]))
        group['interfaces'].append(dict(name=interface,type='other'))
        link=links.get(interface,'')
        function=dict(address=address,interface=interface,driver=driver,driver_version=values.get('version',''),firmware=values.get('firmware-version',''),physical_port_name=port.get('physical_port_name',''))
        for name,pattern in [('speed',r'^\s*Speed:\s*(.+)$'),('duplex',r'^\s*Duplex:\s*(.+)$'),('link_detected',r'^\s*Link detected:\s*(.+)$')]:
            observed=first(link,pattern)
            if observed:function[name]=observed
        group['functions'].append(function)
    cards=[]
    for group in groups.values():
        group['interfaces'].sort(key=lambda p:p['name']);group['functions'].sort(key=lambda p:(p['address'],p['interface']))
        addresses=sorted({f['address'] for f in group['functions']});position=addresses[0]
        cards.append(dict(group,bay='NIC '+position,position=position,
                          driver=', '.join(sorted({f['driver'] for f in group['functions'] if f['driver']})),
                          firmware=', '.join(sorted({f['firmware'] for f in group['functions'] if f['firmware']})),
                          pci_endpoints=[dict(address=address,function='NIC') for address in addresses]))
    return dict(cards=cards,warnings=warnings)


def netbox_transient(result):
    """Retry confirmed gateway/service errors, never permanent validation errors."""
    if not result.get('failed',False):return False
    codes=[];messages=[]
    def inspect(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if key.lower() in ['status','status_code','http_status','http_status_code'] and str(child).isdigit():
                    codes.append(int(child))
                else:inspect(child)
        elif isinstance(value,list):
            for child in value:inspect(child)
        elif isinstance(value,str):messages.append(value)
    inspect(result)
    for message in messages:
        codes.extend(int(code) for code in re.findall(r'(?i)\b(?:HTTP(?: status)?|status(?:_code)?|code)\s*[:=]?\s*(\d{3})\b',message))
        codes.extend(int(code) for code in re.findall(r'(?i)\b(\d{3})\s+(?:Bad Request|Service Unavailable|Bad Gateway|Gateway Timeout|Unauthorized|Forbidden|Not Found)\b',message))
    if any(400<=code<500 for code in codes):return False
    if codes:return any(code in [502,503,504] for code in codes)
    return any(message.strip().lower().rstrip('.') in ['service temporarily unavailable','service unavailable','bad gateway','gateway timeout'] for message in messages)

def unique_module_types(modules):
    seen=set();result=[]
    for module in modules:
        key=(module['manufacturer'],module['model'])
        if key not in seen:seen.add(key);result.append(module)
    return result

def module_type_ids(probes):
    import json
    return {json.dumps([p['item']['manufacturer'],p['item']['model']]):p['module_type']['id'] for p in probes if not p.get('skipped')}


# FRU is optional. Values are observations, never evidence of an absent component.
IDENTITY_PLACEHOLDERS = {'', 'unknown', 'none', 'n/a', 'not specified', 'not available',
    'not applicable', 'unavailable', 'default string', 'system serial number',
    'chassis serial number', 'no asset information', 'unspecified'}


def identity_value(value):
    value = str(value or '').strip()
    compact = re.sub(r'[^a-z0-9]', '', value.lower())
    if value.lower() in IDENTITY_PLACEHOLDERS or compact.startswith('tobefilledbyoem'):
        return ''
    if compact and set(compact) in ({'0'}, {'f'}):
        return ''
    return value


def identity_model(value):
    value = identity_value(value)
    # Some BMCs put a build date in Product Name or Chassis Part Number.
    if re.fullmatch(r'(?i)(?:\d{1,2}[-/ ](?:[a-z]{3,9}|\d{1,2})[-/ ]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})', value):
        return ''
    return value


def fru_identity(probe, facts=None, overrides=None, chassis_probe=None, fru_id='0'):
    """Keep FRUs separate; only the explicitly selected system FRU fills DMI gaps."""
    facts = facts or {}; overrides = overrides or {}; chassis_probe = chassis_probe or {}
    records = []; current = None; warnings = []
    if probe.get('rc', 1) == 0:
        for line in probe.get('stdout', '').replace('\r', '').splitlines():
            header = re.match(r'^\s*FRU Device Description\s*:\s*(.*?)\s*\(ID\s+(\d+)\)\s*$', line)
            if header:
                current = dict(id=header[2], description=header[1], fields={})
                records.append(current)
                continue
            field = re.match(r'^\s*((?:Chassis|Board|Product) [^:]+?)\s*:\s*(.*?)\s*$', line)
            if field and current is not None:
                key, value = field[1].strip(), identity_value(field[2])
                if value:
                    # Repeated Extra fields are common; conflicting identity fields
                    # must not silently select the last serial/model.
                    if key in current['fields'] and current['fields'][key] != value:
                        if key.endswith(' Extra'):
                            current['fields'][key] += '\n' + value
                        else:
                            current.setdefault('ambiguous', []).append(key)
                            warnings.append('Conflicting FRU field: ' + key)
                    else:
                        current['fields'][key] = value
    else:
        warnings.append('IPMI FRU unavailable; existing values preserved')
    selected = [r for r in records if r['id'] == str(fru_id)]
    record = selected[0] if len(selected) == 1 else None
    if records and record is None:
        warnings.append('System FRU ID missing or ambiguous; no FRU identity fallback')
    fields = record['fields'] if record else {}
    sources = {}; hardware = {}; identity = {}

    def choose(target, candidates, model=False, destination=None):
        clean = identity_model if model else identity_value
        for raw, source in candidates:
            value = clean(raw)
            if value:
                (identity if destination is None else destination)[target] = value
                sources[target] = source
                return value
        return ''

    def fru(label):
        if record is None or label in record.get('ambiguous', []):
            return ('', '')
        return (fields.get(label, ''), 'ipmitool fru ID ' + str(fru_id) + ': ' + label)

    choose('serial', [(overrides.get('serial'), 'bootstrap_chassis_serial'),
        (chassis_probe.get('stdout') if chassis_probe.get('rc', 1) == 0 else facts.get('chassis_serial'), 'Linux DMI chassis_serial'), fru('Chassis Serial')])
    choose('manufacturer', [(overrides.get('manufacturer'), 'bootstrap_manufacturer'),
        (facts.get('system_vendor'), 'Linux DMI system_vendor'), fru('Product Manufacturer')])
    choose('model', [(overrides.get('model'), 'bootstrap_device_type'),
        (facts.get('product_name'), 'Linux DMI product_name'), fru('Product Name'),
        fru('Product Part Number'), fru('Chassis Part Number')], model=True)
    mappings = {
        'motherboard_manufacturer': ('board_vendor', 'Board Mfg'),
        'motherboard_model': ('board_name', 'Board Product'),
        'motherboard_serial': ('board_serial', 'Board Serial'),
        'motherboard_part_number': ('', 'Board Part Number'),
        'motherboard_manufacture_date': ('', 'Board Mfg Date'),
        'product_serial': ('product_serial', 'Product Serial'),
        'product_manufacturer': ('system_vendor', 'Product Manufacturer'),
        'product_name': ('product_name', 'Product Name'),
        'product_part_number': ('', 'Product Part Number'),
        'product_version': ('product_version', 'Product Version'),
        'chassis_part_number': ('', 'Chassis Part Number'),
        'chassis_type': ('', 'Chassis Type'),
    }
    for target, (fact, label) in mappings.items():
        choose(target, [(facts.get(fact), 'Linux DMI ' + fact), fru(label)], destination=hardware)
    components = []
    if all(hardware.get(k) for k in ('motherboard_serial', 'motherboard_manufacturer', 'motherboard_model')) and identity_model(hardware['motherboard_model']):
        components.append(dict(name='Motherboard', kind='Motherboard',
            model=hardware['motherboard_model'], part=hardware.get('motherboard_part_number', ''),
            serial=hardware['motherboard_serial'], manufacturer=hardware['motherboard_manufacturer']))
    return dict(identity=identity, hardware_fields=hardware, sources=sources,
                records=records, components=components, warnings=warnings)


def identity_metadata(discovery, existing=None):
    """Merge partial observations without clearing previous fields or FRU records."""
    existing = existing or {}; result = dict(discovery['hardware_fields'])
    sources = dict(existing.get('hardware_identity_sources') or {})
    sources.update(discovery['sources'])
    if sources:
        result['hardware_identity_sources'] = sources
    # JSON objects with an `id` member inside a list are interpreted as related
    # NetBox objects by pynetbox serialization. Key records by FRU ID instead.
    previous_records = existing.get('fru_inventory') or {}
    if isinstance(previous_records, list):
        previous_records = {str(r['id']): r for r in previous_records if isinstance(r, dict) and 'id' in r}
    records = dict(previous_records)
    for record in discovery['records']:
        previous = records.get(record['id'], {})
        records[record['id']] = dict(description=record['description'],
            fields=dict(previous.get('fields', {}), **record['fields']))
        if record.get('ambiguous'):
            records[record['id']]['ambiguous'] = record['ambiguous']
    if records:
        result['fru_inventory'] = records
    return result


class FilterModule:
    def filters(self):
        return {'fhs_fru_identity':fru_identity,'fhs_identity_metadata':identity_metadata,'fhs_fpga_cards':cards,'fhs_fpga_modules':modules,'fhs_nic_vpd':vpd,'fhs_nic_candidates':nic_candidates,'fhs_nic_cards':nic_cards,'fhs_netbox_transient':netbox_transient,'fhs_unique_module_types':unique_module_types,'fhs_module_type_ids':module_type_ids}
