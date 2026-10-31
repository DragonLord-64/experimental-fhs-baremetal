"""Ironic database reconciliation and explicit native lifecycle operations."""
import json
import os
from pathlib import Path
from .common import Error, ROOT, is_nexus, run, temp_json, workspace, yaml_load, protected_yaml

DEFAULT_CLEAN = [{'interface': 'deploy', 'step': 'erase_devices_metadata'}]
STATES = {'manage': {'enroll', 'available'}, 'inspect': {'manageable'},
          'clean': {'manageable'}, 'provide': {'manageable'},
          'deploy': {'available'}, 'adopt': {'manageable'}}


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
    individual = values.get('devices', {}).get(host.get('uuid'), values.get('devices', {}).get(host.get('name'), {}))
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

    def reconcile(self, host, create=False, plan=False):
        if is_nexus(host):
            raise Error('Switches cannot enter the Ironic lifecycle')
        by_id = self.api.find_node(host['uuid']) if host.get('uuid') else None
        by_name = self.api.find_node(host['name']) if host.get('name') else None
        if by_id and by_name and normalize(by_id)['uuid'] != normalize(by_name)['uuid']:
            raise Error('Ironic UUID/name identity conflict')
        old = normalize(by_id or by_name) if by_id or by_name else None
        if host.get('uuid') and not by_id and by_name:
            raise Error('Requested UUID differs from existing named registration')
        if host.get('uuid') and not by_id:
            raise Error('Linked Ironic UUID is missing; resolve the stale identity before enrollment')
        if not old and not create:
            raise Error('Node is not enrolled; use node enroll')
        if old and host.get('serial'):
            serial = (old.get('properties') or {}).get('serial_number')
            if not serial:
                record = self.inspection(old['uuid'])
                serial = record.get('inventory', record).get('system_vendor', {}).get('serial_number')
            if not serial or serial != host['serial']:
                raise Error('Ironic serial conflicts with approved physical identity')
        nics = host.get('nics', [])
        addresses = [str(n['mac']).lower() for n in nics]
        if len(set(addresses)) != len(addresses):
            raise Error('Duplicate provisioning MAC')
        owned_ports = {}
        for address in addresses:
            ports = [normalize(p) for p in self.api.ports(address=address)]
            if len(ports) > 1 or ports and (not old or ports[0].get('node_id', ports[0].get('node_uuid')) != old['uuid']):
                raise Error('Provisioning MAC belongs to another registration')
            owned_ports[address] = ports
        if old and addresses:
            existing = [normalize(p) for p in self.api.ports(node_uuid=old['uuid'])]
            pxe = {str(p['address']).lower() for p in existing if p.get('is_pxe_enabled', p.get('pxe_enabled', True))}
            if pxe and pxe != set(addresses):
                raise Error('Provisioning MAC conflicts with existing boot ports')
        attrs = {key: host[key] for key in ('name', 'driver', 'boot_interface', 'properties', 'instance_info') if host.get(key) is not None}
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
            return old or dict(uuid=host.get('uuid'), provision_state='enroll', maintenance=False)
        if old:
            result = normalize(self.api.update_node(old['uuid'], retry_on_conflict=False, **attrs))
        else:
            if not attrs.get('driver') or not attrs['driver_info'] or not host.get('nics'):
                raise Error('Enrollment needs driver, driver_info and provisioning nics')
            if host.get('uuid'):
                attrs['uuid'] = host['uuid']
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
        print(uuid+': '+action, flush=True)
        if action == 'deploy':
            from .provision import bifrost_deploy
            bifrost_deploy(dict(host, uuid=uuid), options)
        else:
            argv = ['baremetal', 'node', action, '--wait', str(timeout())]
            if action == 'clean':
                # stdin avoids clean-step args (which can include secrets) in argv.
                argv += ['--clean-steps', '-']
            argv.append(uuid)
            run(argv, timeout=timeout()+30, data=json.dumps(steps or DEFAULT_CLEAN) if action == 'clean' else None)
        final = self.get(uuid)
        expected = {'manage': 'manageable', 'inspect': 'manageable', 'clean': 'manageable',
                    'provide': 'available', 'deploy': 'active', 'adopt': 'active'}[action]
        if final['provision_state'] != expected:
            raise Error('Operation did not reach expected state; inspect before retrying')
