"""Actual Ansible inventory invocation; no host connections are made here."""
import ipaddress
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile

from inventory import LabError, OWNER, PREFIX, SITE, tagged, ident

ROOT = Path(__file__).resolve().parent


def inventory_value(value):
    # ansible-core 2.20's inventory JSON encoder wraps untrusted strings.
    # Decode only its exact string marker for comparison; never evaluate it.
    if set(value) == {'__ansible_unsafe'}:
        if not isinstance(value['__ansible_unsafe'], str):
            raise LabError('Malformed Ansible inventory unsafe string marker')
        return value['__ansible_unsafe']
    return value


def failure_category(stderr):
    # Fixed diagnostics only: never pass through CLI output, URLs or records.
    text = stderr.lower()
    categories = [
        ('no module named', 'missing Python dependency'),
        ('requires the', 'missing plugin dependency'),
        ('401', 'API authentication rejected'),
        ('403', 'API permission rejected'),
        ('404', 'API path absent'),
        ('400', 'API query rejected'),
        ('timed out', 'API request timed out'),
        ('connection refused', 'API connection refused'),
        ('could not resolve', 'plugin unavailable'),
        ('template', 'inventory expression evaluation failed'),
        ('undefined', 'inventory field undefined'),
        ('openapi', 'NetBox API schema incompatible'),
        ('schema', 'NetBox API schema incompatible'),
        ('invalid choice', 'plugin option incompatible'),
        ('failed to parse', 'inventory source parse failed'),
        ('could not be verified', 'inventory source verification failed'),
        ('not trusted', 'inventory expression trust rejected'),
        ('unsupported', 'unsupported plugin operation or option'),
        ('not a valid', 'invalid plugin value'),
        ('could not find', 'required plugin resource absent'),
        ('unable to parse', 'inventory source parse failed'),
        ('could not set', 'composed inventory variable evaluation failed'),
        ('has no attribute', 'inventory expression attribute absent'),
        ('untrusted', 'inventory expression trust rejected'),
        ('not allowed', 'inventory expression operation rejected'),
        ('syntax error', 'inventory expression syntax error'),
        ('primary_ip4', 'diagnostic references primary_ip4'),
        ("'address'", 'diagnostic references address attribute'),
        ("'str'", 'diagnostic references string type'),
        ('nonetype', 'diagnostic references null type'),
        ('access to attribute', 'inventory expression attribute access rejected'),
    ]
    matched = list(dict.fromkeys(category for needle, category in categories if needle in text))
    # Exception types are selected from a fixed vocabulary, never copied from
    # arbitrary exception messages (which may contain tokens or API records).
    exceptions = [name for name in ('KeyError', 'TypeError', 'ValueError',
        'AttributeError', 'ImportError', 'ModuleNotFoundError', 'SyntaxError',
        'AnsibleParserError', 'AnsibleError', 'HTTPError', 'ConnectionError')
        if re.search(r'\b' + name + r'\b', stderr)]
    return '; '.join(matched + exceptions) or 'unclassified sanitized CLI failure'


def check_runtime(binary, env):
    version = subprocess.run([binary, '--version'], env=env, capture_output=True,
                             text=True, timeout=20)
    if version.returncode or not re.search(r'\[core 2\.20\.1\]', version.stdout):
        raise LabError('Lab requires pinned ansible-core 2.20.1')
    galaxy = str(Path(binary).with_name('ansible-galaxy'))
    result = subprocess.run([galaxy, 'collection', 'list', 'netbox.netbox', '--format', 'json'],
                            env=env, capture_output=True, text=True, timeout=20)
    try:
        versions = {collections['netbox.netbox']['version']
                    for collections in json.loads(result.stdout).values()
                    if 'netbox.netbox' in collections}
    except (ValueError, KeyError, TypeError):
        raise LabError('Could not verify NetBox collection version') from None
    if result.returncode or versions != {'3.21.0'}:
        raise LabError('Lab requires pinned netbox.netbox 3.21.0 without ambiguous installations')


def ansible_inventory(api, binary='ansible-inventory'):
    # Do not permit the plugin's permissive empty-inventory fallback or a cache.
    with tempfile.TemporaryDirectory(prefix='fhs-nb-ansible-') as directory:
        config = Path(directory) / 'ansible.cfg'
        config.write_text('[defaults]\nlocal_tmp=' + directory + '/tmp\n'
                          '[inventory]\nenable_plugins=netbox.netbox.nb_inventory\n'
                          'unparsed_is_failed=True\nany_unparsed_is_failed=True\ncache=False\n')
        env = {**os.environ, 'ANSIBLE_CONFIG': str(config), 'ANSIBLE_LOCAL_TEMP': directory + '/tmp',
               'ANSIBLE_INVENTORY_UNPARSED_IS_FAILED': 'true',
               'ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED': 'true',
               'NETBOX_API': api.base.rstrip('/'), 'NETBOX_TOKEN': api.token}
        check_runtime(binary, env)
        result = subprocess.run([binary, '-i', str(ROOT / 'lab.netbox.yml'), '--list'],
                                env=env, capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise LabError('Actual NetBox inventory plugin failed: ' + failure_category(result.stderr))
        try:
            inventory = json.loads(result.stdout, object_hook=inventory_value)
            hosts = inventory['_meta']['hostvars']
        except (ValueError, KeyError, TypeError):
            raise LabError('Actual inventory plugin returned malformed output') from None
        if not hosts:
            raise LabError('Actual inventory plugin returned no hosts')
        return inventory


def assert_inventory(api, result):
    records = api.records('dcim/devices/', tag=OWNER, site=SITE, status='active')
    expected = {row['name']: row for row in records}
    hosts = result['_meta']['hostvars']
    if set(hosts) != set(expected):
        raise LabError('Actual inventory membership differs from active owned NetBox devices')
    # One paginated query for the selected devices, including interfaces whose
    # ownership tags an operator changed. Filtering by interface tag would hide
    # those changes and weaken the exact native comparison below.
    interfaces = {row['id']: [] for row in records}
    if interfaces:
        for port in api.records('dcim/interfaces/', device_id=list(interfaces)):
            device = ident(port['device'])
            if device not in interfaces:
                raise LabError('Native interface query returned an unselected device')
            interfaces[device].append(port)
    assigned_ips = {}
    selected_ports = {port['id'] for ports in interfaces.values() for port in ports}
    if interfaces:
        for address in api.records('ipam/ip-addresses/', device_id=list(interfaces),
                                   assigned_to_interface='true'):
            if (address.get('assigned_object_type') != 'dcim.interface' or
                    address.get('assigned_object_id') not in selected_ports):
                raise LabError('Native IP query returned an unselected assignment')
            assigned_ips.setdefault(address['assigned_object_id'], []).append(address)
    kinds = {'logical': set(), 'provisioning': set(), 'reachable': set()}
    for name, host in hosts.items():
        row = expected[name]
        if not name.startswith(PREFIX) or not tagged(row, OWNER):
            raise LabError('Inventory includes unowned host')
        try:
            primary = str(ipaddress.ip_interface(row['primary_ip4']['address']).ip)
            oob = str(ipaddress.ip_interface(row['oob_ip']['address']).ip)
            kind = row['custom_fields']['fhs_lab']['kind']
            for field, expected_value in [('ansible_host', primary), ('primary_ip4', primary),
                    ('oob_ip', oob), ('custom_fields', {k: v for k, v in row['custom_fields'].items()
                                                     if v is not None})]:
                if host.get(field) != expected_value:
                    reason = ('absent' if field not in host else
                              'type differs' if type(host[field]) is not type(expected_value) else
                              'value differs')
                    raise LabError('Actual inventory field mismatch: ' + field + ' (' + reason + ')')
            if not host.get('interfaces'):
                raise LabError('Actual inventory interfaces missing')
            # Prove native interface names, MAC pointers, tags and assigned IPs survive plugin mapping.
            native = interfaces[row['id']]
            actual = {p['name']: p for p in host['interfaces']}
            if set(actual) != {p['name'] for p in native}:
                raise LabError('Actual inventory interface names mismatch')
            for port in native:
                mapped = actual[port['name']]
                if mapped.get('primary_mac_address') != port.get('primary_mac_address'):
                    raise LabError('Actual inventory interface primary MAC mismatch')
                if mapped['mgmt_only'] != port['mgmt_only']:
                    raise LabError('Actual inventory interface management flag mismatch')
                if set(mapped['tags']) != {t['slug'] for t in port['tags']}:
                    raise LabError('Actual inventory interface tags mismatch')
                # The pinned plugin removes redundant assignment pointers only.
                expected_ips = [{k: v for k, v in address.items() if k not in
                    {'assigned_object_id', 'assigned_object_type', 'assigned_object'}}
                    for address in assigned_ips.get(port['id'], [])]
                actual_ips = mapped.get('ip_addresses')
                if (not isinstance(actual_ips, list) or
                        sorted(actual_ips, key=lambda ip: ip['id']) !=
                        sorted(expected_ips, key=lambda ip: ip['id'])):
                    raise LabError('Actual inventory interface assigned IP mismatch')
            kinds[kind].add(name)
        except (KeyError, ValueError, TypeError):
            raise LabError('Actual inventory lost native endpoint/interface/custom-field semantics') from None
    for kind, members in kinds.items():
        if set(result.get('lab_' + kind, {}).get('hosts', [])) != members:
            raise LabError('Actual inventory group membership mismatch')
    return {kind: len(members) for kind, members in kinds.items()}
