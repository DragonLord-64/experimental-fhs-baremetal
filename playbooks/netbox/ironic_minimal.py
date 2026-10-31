"""Minimal pre-OS Ironic inspection import, using native NetBox objects."""
import ipaddress
import os
from pathlib import Path
import re
import sys
import traceback

# Reuse native importer API, serial validation, manufacturer and FRU parsers.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'module_utils'))
def __getattr__(name):
    # Keep standalone help available without optional NetBox dependencies.
    if name == 'Sync':
        from fhs_netbox import Sync
        return Sync
    raise AttributeError(name)


def boot_port(record, onboard_interfaces=()):
    inventory = record.get('inventory', record)
    boot = inventory.get('boot', {})
    mac = str(boot.get('pxe_interface', '')).lower().replace('-', ':')
    if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', mac) or mac == '00:00:00:00:00:00':
        raise ValueError('Inspection needs the actual boot PXE MAC')
    ports = [p for p in inventory.get('interfaces', []) if str(p.get('mac_address', '')).lower() == mac]
    if len(ports) != 1:
        raise ValueError('Boot MAC must match exactly one inspected interface')
    port = ports[0]
    # No universal PCI/driver heuristic: qualification must be explicit.
    if not (port.get('onboard') is True or port.get('name') in onboard_interfaces):
        raise ValueError('Boot interface lacks approved motherboard qualification; configure onboard_interfaces after review')
    return {'name': port['name'], 'mac': mac}


def fru_identity(text, fru_id='0'):
    from fhs_netbox import physical_serial
    import importlib.util
    spec = importlib.util.spec_from_file_location('hwmanage_fru', HERE/'filter_plugins/fhs_inventory.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    result = helper.fru_identity({'rc': 0, 'stdout': text}, fru_id=fru_id)
    identity = result['identity']
    identity['serial'] = physical_serial(identity.get('serial'))
    return identity


def observation(node, record, settings, probe):
    from fhs_netbox import physical_serial
    inventory = record.get('inventory', record)
    port = boot_port(record, settings.get('onboard_interfaces', []))
    # SMBIOS system_vendor.serial_number is not proof of FRU Product Serial.
    # A controller IPMI FRU read remains the default, independent of Linux/SSH.
    identity = fru_identity(probe(node, inventory), str(settings.get('system_fru_id', '0')))
    observed = inventory.get('system_vendor', {}).get('serial_number')
    if observed and physical_serial(observed) != identity['serial']:
        raise ValueError('Inspection serial conflicts with verified FRU Product Serial')
    bmc = str(ipaddress.ip_address(inventory.get('bmc_address') or node.get('driver_info', {}).get('ipmi_address', '')))
    return dict(uuid=node['uuid'], serial=identity['serial'], name=identity['serial'],
                manufacturer=identity.get('manufacturer'), model=identity.get('model'),
                bmc=bmc, port=port)


def remote_fru(node, inventory):
    """Read the selected BMC without credentials in argv or output diagnostics."""
    from hwmanage_lib.common import Error, run
    from hwmanage_lib.ironic import credentials
    driver = credentials(node)
    address = inventory.get('bmc_address') or driver.get('ipmi_address')
    username = driver.get('ipmi_username') or driver.get('redfish_username')
    password = driver.get('ipmi_password') or driver.get('redfish_password')
    if not address or not username or not password or set(str(password)) == {'*'}:
        raise Error('Protected BMC credentials are required for controller-side FRU verification')
    env = dict(os.environ, IPMI_PASSWORD=password, IPMITOOL_PASSWORD=password, LC_ALL='C')
    return run(['ipmitool', '-I', 'lanplus', '-H', address, '-p', str(driver.get('ipmi_port', 623)),
                '-U', username, '-E', '-N', '5', '-R', '1', 'fru'], env=env, timeout=60)


def unique(rows):
    if len(rows) > 1:
        raise ValueError('Duplicate physical identity in NetBox; resolve before import')
    return rows[0] if rows else None


def resolve_device(sync, item):
    from fhs_netbox import physical_serial
    serial = physical_serial(item['serial'])
    by_serial = unique(sync.list('dcim/devices/', serial=serial))
    by_uuid = unique([d for d in sync.list('dcim/devices/')
                      if (d.get('custom_fields') or {}).get('ironic_uuid') == item['uuid']])
    by_name = unique(sync.list('dcim/devices/', name=item['name']))
    matches = [d for d in (by_serial, by_uuid, by_name) if d]
    if len({d['id'] for d in matches}) > 1:
        raise ValueError('Serial, UUID and default name identify different NetBox devices')
    old = matches[0] if matches else None
    if old and (old.get('serial') != serial or
                (old.get('custom_fields') or {}).get('ironic_uuid') not in (None, '', item['uuid'])):
        raise ValueError('Existing device has a conflicting serial or Ironic UUID')
    return old


def apply(sync, item, settings):
    from fhs_netbox import scalar
    old = resolve_device(sync, item)
    # Validate configuration/ownership before any write, including on repeated import.
    if not old and not all(settings.get(k) for k in ('site', 'role', 'device_type')):
        raise ValueError('New devices require explicit numeric site, role and device_type settings')
    ports = sync.list('dcim/interfaces/', device_id=old['id']) if old else []
    tagged = [p for p in ports if any(t.get('slug') == 'provisioning-interface' for t in p.get('tags', []))]
    if len(tagged) > 1 or tagged and tagged[0]['name'] != item['port']['name']:
        raise ValueError('Existing provisioning interface differs; preserve operator inventory')
    for port in ports:
        mac = (port.get('primary_mac_address') or {}).get('mac_address') or port.get('mac_address')
        if port['name'] == item['port']['name'] and mac and mac.lower() != item['port']['mac']:
            raise ValueError('Provisioning interface MAC identity conflict')
    mac_old = sync.find('dcim/mac-addresses/', mac_address=item['port']['mac'].upper())
    expected = next((p['id'] for p in ports if p['name'] == item['port']['name']), None)
    if mac_old and mac_old.get('assigned_object_id') not in (None, expected):
        raise ValueError('Provisioning MAC is already assigned elsewhere')
    prefix = '/128' if ':' in item['bmc'] else '/32'
    bmc_old = sync.find('ipam/ip-addresses/', address=item['bmc']+prefix)
    management = next((p for p in ports if p['name'] == 'bmc'), None)
    if bmc_old and bmc_old.get('assigned_object_id') not in (None, (management or {}).get('id')):
        raise ValueError('BMC IP is already assigned elsewhere')
    if management and (not management.get('mgmt_only') or management['name'] == item['port']['name']):
        raise ValueError('Existing BMC interface has conflicting purpose')
    if old and old.get('oob_ip') and old['oob_ip'].get('address', '').split('/')[0] != item['bmc']:
        raise ValueError('Existing BMC address conflicts with observed identity')
    sync.ensure('extras/custom-fields/', {'name': 'ironic_uuid'},
                {'name': 'ironic_uuid', 'type': 'text', 'object_types': ['dcim.device']}, 'Ironic UUID field')
    if old:
        # Do not change name, status, primary IP, tags, role or deployment context.
        data = {'custom_fields': {'ironic_uuid': item['uuid']}}
        key = {'id': old['id']}
    else:
        data = {k: int(settings[k]) for k in ('site', 'role', 'device_type')}
        data.update(name=item['name'], serial=item['serial'], status='planned',
                    custom_fields={'ironic_uuid': item['uuid']})
        key = {'name': item['name']}
    device = sync.ensure('dcim/devices/', key, data, 'discovered chassis')
    tag = sync.ensure('extras/tags/', {'slug': 'provisioning-interface'},
                      {'name': 'provisioning-interface', 'slug': 'provisioning-interface'}, 'provisioning tag')
    prior = next((p for p in ports if p['name'] == item['port']['name']), {})
    tags = list(dict.fromkeys([scalar(t) for t in prior.get('tags', [])]+[tag['id']]))
    nic = sync.ensure('dcim/interfaces/', {'device_id': device['id'], 'name': item['port']['name']},
                      dict(device=device['id'], name=item['port']['name'], type=scalar(prior.get('type')) or 'other', tags=tags), 'boot interface')
    mac = sync.ensure('dcim/mac-addresses/', {'mac_address': item['port']['mac'].upper()},
                      dict(mac_address=item['port']['mac'].upper(), assigned_object_type='dcim.interface',
                           assigned_object_id=nic['id']), 'boot MAC')
    sync.ensure('dcim/interfaces/', {'id': nic['id']}, {'primary_mac_address': mac['id']}, 'primary boot MAC')
    bmc = sync.ensure('dcim/interfaces/', {'device_id': device['id'], 'name': 'bmc'},
                      dict(device=device['id'], name='bmc', type='other', mgmt_only=True), 'BMC interface')
    ip = sync.ensure('ipam/ip-addresses/', {'address': item['bmc']+prefix},
                     dict(address=item['bmc']+prefix, status='active', assigned_object_type='dcim.interface',
                          assigned_object_id=bmc['id']), 'BMC address')
    sync.ensure('dcim/devices/', {'id': device['id']}, {'oob_ip': ip['id']}, 'native out-of-band IP')
    return device


def import_nodes(nodes, ironic, settings, sync, probe=remote_fru):
    items = [observation(n, ironic.inspection(n['uuid']), settings, probe) for n in nodes.values()]
    if len({i['serial'] for i in items}) != len(items) or len({i['bmc'] for i in items}) != len(items):
        raise ValueError('Selected discoveries contain duplicate chassis identities')
    # Resolve all physical identity conflicts before creating anything.
    for item in items:
        resolve_device(sync, item)
    return [apply(sync, item, settings) for item in items]


def import_selected(nodes, ironic, *, plan=False):
    """Shared import service for the optional wrapper and standalone entry point."""
    from fhs_netbox import Sync
    from hwmanage_lib.common import yaml_load
    from hwmanage_lib.inventory import netbox_api
    api = netbox_api()
    settings = yaml_load(os.environ.get('HWMANAGE_IMPORT_DEFAULTS', str(HERE.parents[1]/'scripts/hwmanage/import.yml')))
    token = api.session.headers['Authorization'].split(' ', 1)[1]
    sync = Sync({'netbox_url': api.base[:-5], 'netbox_token': token,
                 'validate_certs': api.session.verify}, plan)
    return import_nodes(nodes, ironic, settings, sync)


def main(argv=None):
    """Standalone pre-OS import; deliberately independent of hwmanage_lib.cli."""
    import argparse
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            self.print_usage(sys.stderr)
            self.exit(2, 'Invalid or missing arguments; use --help.\n')
    parser = Parser(description='Import saved Ironic inspections and verified FRU identity into NetBox.')
    targets = parser.add_mutually_exclusive_group(required=True)
    targets.add_argument('--limit', help='One exact Ironic UUID or name')
    targets.add_argument('--all', action='store_true', help='Import all Ironic discoveries, including unnamed nodes')
    targets.add_argument('--selected-uuids', help=argparse.SUPPRESS)
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Show remote application output')
    parser.add_argument('--plan', action='store_true', help='Validate without NetBox writes')
    args = parser.parse_args(argv)
    if args.verbose:
        os.environ["HWMANAGE_VERBOSE"] = str(args.verbose)
    sys.path.insert(0, str(HERE.parents[1]/'scripts/hwmanage'))
    from hwmanage_lib.common import Error
    from hwmanage_lib.ironic import Ironic
    try:
        ironic = Ironic()
        if args.selected_uuids is not None:
            import json
            from uuid import UUID
            selected = json.loads(args.selected_uuids)
            if not isinstance(selected, list) or not selected or any(not isinstance(u, str) or str(UUID(u)) != u for u in selected) or len(set(selected)) != len(selected):
                raise Error('Selected Ironic UUIDs must be a nonempty unique list')
            nodes = {u: ironic.get(u) for u in selected}
            if any(node.get('uuid') != u for u, node in nodes.items()):
                raise Error('Selected Ironic UUID identity changed')
        else:
            nodes = ironic.targets(args.limit)
        result = import_selected(nodes, ironic, plan=args.plan)
        print(str(len(result))+' minimal device(s) '+('planned' if args.plan else 'imported'))
        return 0
    except Error as error:
        print(str(error), file=sys.stderr)
    except Exception:
        traceback.print_exc()
    return 1


if __name__ == '__main__':
    sys.exit(main())
