"""Scoped native Ansible/Bifrost execution."""
import os
from pathlib import Path
from .common import Error, ROOT, run, temp_json, workspace
from .inventory import as_inventory


def deployment_preflight(hosts, options=None):
    """Validate the complete deployment selection without touching lifecycle state."""
    import ipaddress
    import re
    from urllib.parse import urlsplit
    from .ironic import credentials

    def supplied(value):
        text = str(value).strip() if value is not None else ''
        return (bool(text) and not any(marker in text.lower() for marker in
                ('replace', 'changeme', 'change_me', 'placeholder', '{{'))
                and not re.search(r'<[^<>]+>', text)
                and text.lower() not in ('none', 'null', 'todo', 'tbd'))

    play = Path(os.environ.get('HWMANAGE_BIFROST_PLAYBOOKS', '/bifrost/playbooks'))/'deploy-dynamic.yaml'
    if not play.is_file():
        raise Error('Bifrost deploy-dynamic.yaml is unavailable; run inside the provisioning container')
    with workspace() as directory:
        ansible_options(options, directory)
    if not hosts:
        raise Error('Deployment requires selected hosts')
    for host in hosts.values():
        try:
            address = ipaddress.ip_address(host.get('ipv4_address', ''))
            primary = ipaddress.ip_address(host.get('ansible_host', ''))
            if address.version != 4 or address != primary or address.is_unspecified or address.is_multicast:
                raise ValueError
        except ValueError:
            raise Error('Deployment requires an approved primary IPv4 address') from None
        if not any(re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', str(n.get('mac', ''))) and
                   int(str(n['mac']).split(':')[0], 16) % 2 == 0 and
                   str(n['mac']).lower() != '00:00:00:00:00:00'
                   for n in host.get('nics', []) if isinstance(n, dict)):
            raise Error('Deployment requires a valid boot MAC')
        image = host.get('instance_info') or {}
        if not all(supplied(image.get(k)) for k in ('image_source', 'image_checksum')):
            raise Error('Deployment requires image_source and image_checksum')
        root = (host.get('properties') or {}).get('root_device') or host.get('root_device')
        if not isinstance(root, dict) or not root or not all(supplied(v) for v in root.values()):
            raise Error('Deployment requires explicit root_device criteria')
        auth = credentials(host)
        prefix = 'ipmi' if host.get('driver') == 'ipmi' else 'redfish'
        # Protected passwords are opaque secrets, not deployment templates.
        password = auth.get(prefix+'_password')
        if (not all(supplied(auth.get(prefix+'_'+key)) for key in ('address', 'username'))
                or password is None or not str(password).strip()):
            raise Error('Deployment requires protected BMC connection and authentication')
        endpoint = str(auth[prefix+'_address'])
        parsed = urlsplit(endpoint if prefix == 'redfish' else '//'+endpoint)
        if not parsed.hostname or parsed.username or parsed.password or (prefix == 'redfish' and parsed.scheme not in ('http', 'https')):
            raise Error('Deployment requires a usable BMC address')


def ansible_options(options, directory=None):
    args, variables = [], {}
    if options:
        for value in getattr(options, 'extra_vars', []):
            if value.startswith('@'):
                from .common import protected_yaml
                parsed = protected_yaml(value[1:])
            elif value.lstrip().startswith(('{', '[')):
                import json
                parsed = json.loads(value)
            else:
                from ansible.parsing.splitter import parse_kv
                parsed = parse_kv(value)
            if not isinstance(parsed, dict) or '_raw_params' in parsed:
                raise Error('Extra vars must be a mapping or KEY=VALUE assignments')
            # Extra vars must not redirect play hosts, inventory or immutable IDs.
            reserved = {'inventory_hostname', 'inventory_hostname_short', 'groups', 'hostvars',
                        'ansible_play_hosts', 'ansible_play_hosts_all', 'ansible_play_batch',
                        'switch_group', 'netbox_import_hosts', 'uuid', 'name', 'nics',
                        'driver_info', 'host_groups', 'netbox_device_id', 'serial',
                        'ansible_host', 'ipv4_address', 'automated_clean', 'wait_for_node_deploy',
                        'wait_for_node_deploy_timeout', 'wait_timeout', 'ironic_url', 'ironic_api_url'}
            if reserved.intersection(parsed):
                raise Error('Extra vars cannot override resolved target identity or scope')
            variables.update(parsed)
        for key in ('tags', 'skip_tags'):
            if getattr(options, key, None):
                args += ['--'+key.replace('_', '-'), getattr(options, key)]
    if variables:
        if directory is None:
            raise Error('Private extra-vars workspace required')
        args += ['-e', '@'+temp_json(directory, 'extra-vars.json', variables)]
    return args


def apply(hosts, options=None, *, inventory_only=False, wait=False, wait_only=False, plan=False):
    from .ironic import timeout
    wait_timeout = timeout() if wait else None
    if not hosts or any(not h.get('ansible_host') for h in hosts.values()):
        raise Error('Every selected host needs an approved management/primary IP')
    with workspace() as directory:
        args = ansible_options(options, directory)
        if plan:
            return
        source = temp_json(directory, 'inventory.json', as_inventory(hosts))
        sources = ['-i', str(site_vars_source()), '-i', source]
        if wait:
            run(['ansible-playbook', *sources, ROOT/'playbooks/hwmanage_wait.yml', '--limit', ','.join(hosts)],
                timeout=wait_timeout+60)
        if wait_only:
            return
        play = ROOT/'playbooks/provision.yml'
        if inventory_only:
            args = ['--tags', 'inventory']
        run(['ansible-playbook', *sources, play, '--limit', ','.join(hosts), *args],
            timeout=int(os.environ.get('HWMANAGE_ANSIBLE_TIMEOUT', '7200')))


def bifrost_deploy(host, options=None):
    from .ironic import timeout, credentials, registration_name
    directory_root = Path(os.environ.get('HWMANAGE_BIFROST_PLAYBOOKS', '/bifrost/playbooks'))
    play = directory_root/'deploy-dynamic.yaml'
    if not play.is_file():
        raise Error('Bifrost deploy-dynamic.yaml is unavailable; run inside the provisioning container')
    with workspace() as directory:
        host = dict(host, name=registration_name(host), driver_info=credentials(host))
        source = temp_json(directory, 'baremetal.json', {host['name']: host})
        variables = temp_json(directory, 'vars.json', {'wait_for_node_deploy': True,
            'wait_timeout': timeout(), 'automated_clean': False})
        env = dict(os.environ, BIFROST_INVENTORY_SOURCE=source)
        run(['ansible-playbook', '-i', directory_root/'inventory/bifrost_inventory.py',
             '-i', directory_root/'inventory/localhost', play, '--limit', 'localhost,'+host['name'],
             '-e', '@'+variables, *ansible_options(options, directory)], env=env, timeout=timeout()+180)


def site_vars_source():
    """Empty static source loads adjacent group_vars/host_vars without NetBox."""
    source = Path(os.environ.get('HWMANAGE_SITE_INVENTORY', ROOT/'inventory/dev_env/hwmanage-vars.yml'))
    if not source.is_file():
        raise Error('Site variables inventory is unavailable; check inventory.site_variables in config.yml')
    return source


def effective_hosts(hosts):
    """Materialize native Ansible precedence before export or fixed runbooks."""
    import json
    with workspace() as directory:
        source = temp_json(directory, 'inventory.json', as_inventory(hosts))
        data = json.loads(run(['ansible-inventory', '-i', site_vars_source(), '-i', source, '--list']))
    values = data.get('_meta', {}).get('hostvars', {})
    return {name: dict(values.get(name, {}), **host) for name, host in hosts.items()}
