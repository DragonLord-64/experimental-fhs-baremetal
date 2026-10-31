"""Ironic database reconciliation and explicit native lifecycle operations."""
import json
import os
from pathlib import Path
from .common import Error, ROOT, is_nexus, run, temp_json, workspace, yaml_load, protected_yaml, safe_name

DEFAULT_CLEAN = [{'interface': 'deploy', 'step': 'erase_devices_metadata'}]
STATES = {'manage': {'enroll', 'available'}, 'inspect': {'manageable'},
          'clean': {'manageable'}, 'provide': {'manageable'},
          'deploy': {'available'}, 'adopt': {'manageable'}}


def registration_name(host):
    """NetBox product serial is the Ironic name; native input may already be named."""
    serial = host.get('serial') or (host.get('properties') or {}).get('serial_number')
    if serial:
        return safe_name(serial)
    if host.get('netbox_device_id') is not None:
        raise Error('NetBox device needs its product serial before Ironic operations')
    if not host.get('name'):
        raise Error('Ironic node is unnamed; name it with its product serial before lifecycle operations')
    return safe_name(host['name'])


def validate_registration_names(hosts):
    names = [registration_name(h) for h in hosts.values()]
    if len(set(names)) != len(names):
        raise Error('Selected devices have duplicate Ironic serial names; remove the duplicate inventory entry')


def timeout():
    value = int(os.environ.get('HWMANAGE_TIMEOUT', '1800'))
    if value < 900:
        raise Error('HWMANAGE_TIMEOUT must be at least 900 seconds')
    return value


def normalize(node):
    value = node.to_dict() if hasattr(node, 'to_dict') else dict(node)
    value['uuid'] = value.get('uuid') or value.get('id')
    value['maintenance'] = value.get('maintenance', value.get('is_maintenance', False))
    return value


def clean_steps(value=None):
    if value is None:
        return DEFAULT_CLEAN
    import sys
    text = sys.stdin.read() if value == '-' else (Path(value).read_text() if not value.lstrip().startswith('[') else value)
    steps = json.loads(text)
    if not isinstance(steps, list) or not steps or any(not isinstance(s, dict) or
            not all(isinstance(s.get(k), str) and s[k] for k in ('interface', 'step')) or
            set(s) - {'interface', 'step', 'args'} or not isinstance(s.get('args', {}), dict) for s in steps):
        raise Error('Clean steps must be a nonempty JSON list of interface/step/optional args mappings')
    return steps


def guard(node, action, pipeline=False):
    if node.get('maintenance'):
        raise Error('Maintenance node refused')
    state = node.get('provision_state')
    if pipeline:
        if state not in ('enroll', 'manageable', 'available'):
            raise Error('Runbook requires a stable enroll/manageable/available node; never undeploys')
    elif action in STATES and state not in STATES[action]:
        raise Error('Incompatible lifecycle state for '+action)


def automatic_clean_disabled(node):
    policy = node.get('automated_clean')
    if policy is False:
        return
    if policy is True:
        raise Error('Disable automatic cleaning before provide')
    from .config import ironic_policy
    if ironic_policy() is not False:
        raise Error('Effective automated cleaning is not verified disabled')


def credentials(host):
    path = os.environ.get('HWMANAGE_BMC_SECRETS', '/provision/files.d/credentials/redfish.yml')
    values = protected_yaml(path) if Path(path).exists() else {}
    values = values or {}
    values = values.get('redfish_credentials', values)
    defaults = values.get('defaults', {})
    devices = values.get('devices', {})
    individual = devices.get(host.get('serial'), devices.get(host.get('name'), devices.get(host.get('uuid'), {})))
    return dict(host.get('driver_info', {}), **dict(defaults, **individual))


class Ironic:
    def __init__(self, proxy=None):
        if proxy is None:
            try:
                from openstack.connection import Connection
            except ImportError:
                raise Error('Ironic operations require openstacksdk and the baremetal client') from None
            # Environment/clouds.yaml remains the native authentication interface.
            if os.environ.get('OS_CLOUD') or os.environ.get('OS_AUTH_TYPE') not in (None, 'none'):
                connection = Connection(cloud=os.environ.get('OS_CLOUD'))
            else:
                connection = Connection(auth_type='none', baremetal_endpoint_override=os.environ.get(
                    'OS_ENDPOINT', 'http://localhost:6385'), baremetal_api_version='1.82')
            proxy = connection.baremetal
        self.api = proxy

    def targets(self, limit=None):
        rows = [normalize(n) for n in self.api.nodes(details=True)]
        if limit:
            rows = [n for n in rows if limit in (n.get('uuid'), n.get('name'))]
            if len(rows) != 1:
                raise Error('Ironic --limit requires one exact unique name or UUID')
        if not rows:
            raise Error('No Ironic nodes matched')
        return {n['uuid']: n for n in rows}

    def get(self, uuid):
        return normalize(self.api.get_node(uuid))

    def inspection(self, uuid):
        # Native Ironic saved inventory endpoint (API 1.81+), before OS/SSH.
        response = self.api.get('/nodes/'+uuid+'/inventory', microversion='1.82')
        if response.status_code != 200:
            raise Error('Saved Ironic inventory unavailable; inspect the node before import')
        return response.json()

    def ensure_name(self, node, name, *, plan=False):
        """Name this discovery with its verified serial; never replace another node."""
        name = safe_name(name)
        if node.get('name') == name:
            return node
        match = self.api.find_node(name)
        if match and normalize(match)['uuid'] != node['uuid']:
            raise Error('Ironic name '+name+' already belongs to another registration; resolve the duplicate')
        if plan:
            return dict(node, name=name)
        return normalize(self.api.update_node(node['uuid'], retry_on_conflict=False, name=name))

    def reconcile(self, host, create=False, plan=False):
        if is_nexus(host):
            raise Error('Switches cannot enter the Ironic lifecycle')
        name = registration_name(host)
        match = self.api.find_node(name)
        old = normalize(match) if match else None
        nics = host.get('nics', [])
        addresses = [str(n['mac']).lower() for n in nics]
        if len(set(addresses)) != len(addresses):
            raise Error('Duplicate provisioning MAC')
        # Summary port responses omit ownership; request details for identity checks.
        owned_ports = {}
        for address in addresses:
            ports = [normalize(p) for p in self.api.ports(details=True, address=address)]
            if len(ports) > 1:
                raise Error('Provisioning MAC '+address+' has '+str(len(ports))+' matching port(s); owner(s) '+
                            ', '.join(str(p.get('node_id') or p.get('node_uuid')) for p in ports)+
                            '; selected Ironic UUID '+str((old or {}).get('uuid'))+'; ownership preserved')
            owned_ports[address] = ports
        owners = {p.get('node_id') or p.get('node_uuid')
                  for ports in owned_ports.values() for p in ports}
        if None in owners or len(owners) > 1:
            raise Error('Provisioning ports have missing or conflicting Ironic owners')
        if not old and owners:
            # Reuse discovery through its port, including sync before it has a name.
            old = self.get(next(iter(owners)))
        if old and owners and owners != {old['uuid']}:
            raise Error('Ironic serial name and provisioning MAC identify different registrations; ownership preserved')
        if not old and not create:
            raise Error('Ironic node '+name+' is not enrolled; use node enroll')
        if old and addresses:
            # Use the SDK query name, not the resource body's node_uuid field.
            existing = [normalize(p) for p in self.api.ports(details=True, node=old['uuid'])]
            pxe = {str(p['address']).lower() for p in existing if p.get('is_pxe_enabled', p.get('pxe_enabled', True))}
            if pxe and pxe != set(addresses):
                raise Error('Provisioning MAC conflicts with existing boot ports')
        attrs = {key: host[key] for key in ('name', 'driver', 'boot_interface', 'properties', 'instance_info') if host.get(key) is not None}
        attrs['name'] = name
        attrs['driver_info'] = credentials(host)
        if host.get('serial'):
            attrs['properties'] = dict(attrs.get('properties', {}), serial_number=host['serial'])
        for kind, interface in host.get('driver_interfaces', {}).items():
            attrs[kind+'_interface'] = interface
        for kind in ('deploy', 'inspect', 'management', 'power', 'network', 'raid'):
            if kind+'_interface' in host:
                attrs[kind+'_interface'] = host[kind+'_interface']
        # Database-only settings: explicit cleaning is a separate operation.
        attrs['automated_clean'] = False
        if old:
            for field in ('driver_info', 'properties', 'instance_info'):
                attrs[field] = dict(old.get(field) or {}, **attrs.get(field, {}))
        if plan:
            return old or dict(name=name, provision_state='enroll', maintenance=False)
        if old:
            result = normalize(self.api.update_node(old['uuid'], retry_on_conflict=False, **attrs))
        else:
            if not attrs.get('driver') or not attrs['driver_info'] or not host.get('nics'):
                raise Error('Enrollment needs driver, driver_info and provisioning nics')
            result = normalize(self.api.create_node(**attrs))
        for address, ports in owned_ports.items():
            if not ports:
                self.api.create_port(node_uuid=result['uuid'], address=address, pxe_enabled=True)
        return result

    def action(self, node, action, *, steps=None, host=None, options=None, plan=False):
        guard(node, action)
        if action == 'provide':
            automatic_clean_disabled(node)
        if action == 'deploy':
            from .provision import deployment_preflight
            deployment_preflight({node['uuid']: host or {}}, options)
        if plan:
            return
        uuid = node['uuid']
        target = node.get('name') or uuid
        print(target+': '+action, flush=True)
        if action == 'deploy':
            from .provision import bifrost_deploy
            bifrost_deploy(dict(host, uuid=uuid), options)
        else:
            argv = ['baremetal', 'node', action, '--wait', str(timeout())]
            if action == 'clean':
                # stdin avoids clean-step args (which can include secrets) in argv.
                argv += ['--clean-steps', '-']
            argv.append(target)
            run(argv, timeout=timeout()+30, data=json.dumps(steps or DEFAULT_CLEAN) if action == 'clean' else None)
        final = self.get(uuid)
        expected = {'manage': 'manageable', 'inspect': 'manageable', 'clean': 'manageable',
                    'provide': 'available', 'deploy': 'active', 'adopt': 'active'}[action]
        if final['provision_state'] != expected:
            raise Error('Operation did not reach expected state; inspect before retrying')
