"""Resolve an explicit inventory once; never fall back after a service error."""
import json
import os
from .common import Error, ROOT, load_module, private_write, run, safe_name, temp_json, workspace, yaml_load

NATIVE_KEYS = ('driver', 'boot_interface', 'driver_interfaces', 'ipv4_subnet_mask',
               'ipv4_nameserver', 'instance_info', 'properties', 'ipv4_gateway',
               'addressing_mode', 'node_network_data', 'ipa_kernel_url', 'ipa_ramdisk_url')


def netbox_api():
    transfer = load_module('hwmanage_transfer', ROOT / 'playbooks/netbox/netbox_transfer.py')
    secrets = os.environ.get('FHS_PLATFORM_SECRETS_FILE', '/provision/files.d/credentials/platform-secrets.yml')
    endpoint = os.environ.get('FHS_PLATFORM_ENDPOINTS_FILE', '/provision/files.d/platform-endpoints.yml')
    # Existing credential loader supports whole-file and inline Vault values.
    vault_file = os.environ.get('ANSIBLE_VAULT_PASSWORD_FILE')
    vault_args = ['--vault-password-file', vault_file] if vault_file else []
    url = None
    if os.path.exists(endpoint):
        url = yaml_load(endpoint)['netbox_url']
    values = transfer.credentials(secrets, vault_args, netbox_url=url)
    return transfer.API(*values)


def no_context_secrets(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if any(part in key.lower() for part in ('password', 'token', 'secret', 'private_key')):
                raise Error('Credentials belong in protected controller secrets, not config context')
            no_context_secrets(item)
    elif isinstance(value, list):
        for item in value:
            no_context_secrets(item)


def from_netbox(api=None):
    api = api or netbox_api()
    devices = api.rows('dcim/devices/')
    interfaces = api.rows('dcim/interfaces/')
    result = {}
    for device in devices:
        name = safe_name(device.get('name'))
        if name in result:
            raise Error('Ambiguous NetBox hostname')
        context = device.get('config_context') or {}
        no_context_secrets(context)
        role = device.get('role') or device.get('device_role') or {}
        tags = [t['slug'] for t in device.get('tags', [])]
        groups = ['device_roles_'+role['slug']] if role.get('slug') else []
        groups += ['tags_'+t for t in tags]
        if 'ubuntu24-hardening' in tags:
            groups.append('ubuntu24_cis_production')
        if role.get('slug') == 'nexus-switch' or 'nexus-switch' in tags:
            groups.append('nexus')
        host = dict(context, name=name, host_groups=groups, netbox_device_id=device['id'],
                    serial=device.get('serial'), tags=tags,
                    uuid=(device.get('custom_fields') or {}).get('ironic_uuid'))
        primary = device.get('primary_ip4') or {}
        if primary.get('address'):
            host['ansible_host'] = primary['address'].split('/')[0]
            host['ipv4_address'] = host['ansible_host']
        bmc = (device.get('oob_ip') or {}).get('address', '').split('/')[0]
        ports = [p for p in interfaces if (p.get('device') or {}).get('id') == device['id']]
        host['interfaces'] = ports
        provision = [p for p in ports if any(t['slug'] == 'provisioning-interface' for t in p.get('tags', []))]
        if provision:
            if len(provision) != 1 or provision[0].get('mgmt_only') or not provision[0].get('enabled', True):
                raise Error('Provisioning interface must be unique, enabled and not management-only')
            mac = (provision[0].get('primary_mac_address') or {}).get('mac_address') or provision[0].get('mac_address')
            if mac:
                host['nics'] = [{'mac': mac.lower()}]
                host['sys_mac_address'] = mac.lower()
        host['driver_info'] = {'redfish_address': 'https://'+('['+bmc+']' if ':' in bmc else bmc)} if bmc else {}
        if host.get('driver') == 'ipmi' and bmc:
            host['driver_info'] = {'ipmi_address': bmc}
        if 'nexus' in groups:
            host.update(ansible_connection='ansible.netcommon.network_cli', ansible_network_os='cisco.nxos.nxos')
        result[name] = host
    return result


def as_inventory(hosts):
    groups = {'all': {'hosts': {name: dict(host) for name, host in hosts.items()}}}
    for name, host in hosts.items():
        for group in host.get('host_groups', []):
            groups.setdefault(group, {'hosts': {}})['hosts'][name] = {}
    return groups


def select(hosts, pattern=None):
    if not hosts:
        raise Error('Inventory has no hosts')
    if pattern is None:
        return hosts
    # Native Ansible patterns, including intersections, exclusions and groups.
    try:
        from ansible.inventory.manager import InventoryManager
        from ansible.parsing.dataloader import DataLoader
    except ImportError:
        raise Error('Ansible is required to resolve inventory patterns') from None
    with workspace() as directory:
        path = temp_json(directory, 'inventory.json', as_inventory(hosts))
        manager = InventoryManager(loader=DataLoader(), sources=[path])
        names = [h.name for h in manager.get_hosts(pattern=pattern)]
    if not names:
        raise Error('Target pattern matched no hosts')
    return {name: hosts[name] for name in names}


def from_yaml(path):
    document = yaml_load(path)
    if not isinstance(document, dict) or not document:
        raise Error('Expected a nonempty Bifrost mapping or native Ansible inventory')
    if 'all' not in document and all(isinstance(v, dict) and ('driver' in v or 'nics' in v or 'driver_info' in v) for v in document.values()):
        result = {}
        for key, value in document.items():
            name = safe_name(value.get('name') or key)
            if name in result:
                raise Error('Duplicate YAML hostname')
            result[name] = dict(value, name=name,
                host_groups=value.get('host_groups', ['device_roles_fpga-host-server']),
                ansible_host=value.get('ansible_host', value.get('ipv4_address')))
        return result
    data = json.loads(run(['ansible-inventory', '-i', path, '--list']))
    hosts = data.get('_meta', {}).get('hostvars', {})
    # Native --list can omit hostvars for hosts with no variables.
    for group, values in data.items():
        if group != '_meta':
            for name in values.get('hosts', []):
                hosts.setdefault(name, {})
    def members(group, seen=()):
        if group in seen:
            raise Error('Cyclic inventory groups')
        value = data.get(group, {})
        result = set(value.get('hosts', []))
        for child in value.get('children', []):
            result.update(members(child, (*seen, group)))
        return result
    membership = {g: members(g) for g in data if g not in ('_meta', 'all', 'ungrouped')}
    for name, host in hosts.items():
        safe_name(name)
        host['name'] = name
        host['host_groups'] = [g for g, names in membership.items() if name in names]
    return hosts


def resolve(source, limit=None):
    if source == 'ironic':
        from .ironic import Ironic
        return Ironic().targets(limit)
    return select(from_netbox() if source == 'netbox' else from_yaml(source), limit)


def export(hosts, path=None, output_dir=None):
    # Native Bifrost node mapping; no wrapper schema and no service dependency.
    result = {}
    for name, host in hosts.items():
        value = {k: v for k, v in host.items() if k not in ('netbox_device_id', 'interfaces', 'tags')}
        value['driver_info'] = {k: v for k, v in value.get('driver_info', {}).items()
                                if not any(s in k.lower() for s in ('password', 'token', 'secret', 'username'))}
        for key in list(value):
            if any(s in key.lower() for s in ('password', 'token', 'secret', 'private_key')):
                del value[key]
        result[name] = value
    if output_dir:
        from pathlib import Path
        from .provision import effective_hosts
        # Resolve site policy before sanitizing it into a portable snapshot.
        enriched = effective_hosts(hosts)
        for name in result:
            enriched[name].pop('driver_info', None)
            enriched[name].update(result[name])
        def sanitize(value):
            if isinstance(value, dict):
                return {k: sanitize(v) for k, v in value.items() if not any(
                    s in k.lower() for s in ('password', 'token', 'secret', 'private_key', 'username'))}
            if isinstance(value, list):
                return [sanitize(v) for v in value]
            return value
        result = sanitize(enriched)
        root = Path(output_dir)
        root.mkdir(mode=0o700)
        (root/'group_vars').mkdir(mode=0o700)
        private_write(root/'nodes.yml', result)
        private_write(root/'inventory.yml', as_inventory(result))
        private_write(root/'group_vars/baremetal', {'automated_clean': False})
    else:
        private_write(path, result)
