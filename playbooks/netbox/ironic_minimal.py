"""Minimal pre-OS Ironic inspection import, using native NetBox objects."""
import ipaddress
import os
from pathlib import Path
import re
import sys
import traceback
from urllib.parse import urlsplit

# Reuse native importer API, serial validation, manufacturer and FRU parsers.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'module_utils'))
def __getattr__(name):
    # Keep standalone help available without optional NetBox dependencies.
    if name == 'Sync':
        from fhs_netbox import Sync
        return Sync
    raise AttributeError(name)


def boot_port(record, provisioning_interface=None):
    inventory = record.get('inventory', record)
    boot = inventory.get('boot', {})
    mac = str(boot.get('pxe_interface', '')).lower().replace('-', ':')
    if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', mac) or mac == '00:00:00:00:00:00':
        raise ValueError('Inspection needs the actual boot PXE MAC')
    ports = [p for p in inventory.get('interfaces', []) if str(p.get('mac_address', '')).lower() == mac]
    if len(ports) != 1:
        raise ValueError('Boot MAC must match exactly one inspected interface')
    port = ports[0]
    if not isinstance(port.get('name'), str) or not port['name']:
        raise ValueError('Boot interface needs an inspected name')
    if provisioning_interface and port['name'] != provisioning_interface:
        raise ValueError('Configured provisioning_interface conflicts with inspected boot MAC')
    return {'name': port['name'], 'mac': mac}


def bmc_address(node, inventory):
    driver = node.get('driver_info') or {}
    address = inventory.get('bmc_address') or driver.get('ipmi_address')
    if not address and driver.get('redfish_address'):
        address = urlsplit(driver['redfish_address']).hostname
    return str(ipaddress.ip_address(address or ''))


def saved_or_minimal_record(node, ironic, settings):
    from hwmanage_lib.ironic import InventoryUnavailable
    try:
        record = ironic.inspection(node['uuid'])
    except InventoryUnavailable:
        record = {}
        print(node['uuid']+': no saved inventory; using registered PXE port and BMC FRU', flush=True)
    inventory = dict(record.get('inventory', record) or {})
    boot = dict(inventory.get('boot') or {})
    mac = str(boot.get('pxe_interface') or '').lower().replace('-', ':')
    interfaces = [dict(p) for p in (inventory.get('interfaces') or [])]
    matching = [p for p in interfaces if str(p.get('mac_address', '')).lower() == mac] if mac else []
    if mac and len(matching) == 1 and matching[0].get('name'):
        return record
    if mac and (not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', mac) or mac == '00:00:00:00:00:00'):
        raise ValueError('Invalid inspected boot MAC; existing inventory preserved')
    if len(matching) > 1:
        raise ValueError('Boot MAC matches multiple inspected interfaces')
    candidates = []
    for port in ironic.provisioning_ports(node['uuid']):
        enabled = port.get('is_pxe_enabled')
        if enabled is None:
            enabled = port.get('pxe_enabled', True)
        address = str(port.get('address') or '').lower().replace('-', ':')
        if enabled and (not mac or address == mac):
            candidates.append(address)
    if len(candidates) != 1:
        raise ValueError('Minimal import requires exactly one matching registered PXE port')
    mac = candidates[0]
    matching = [p for p in interfaces if str(p.get('mac_address', '')).lower() == mac]
    if len(matching) > 1:
        raise ValueError('Registered PXE MAC matches multiple inspected interfaces')
    actual_name = matching[0].get('name') if matching else None
    name = actual_name or settings.get('provisioning_interface') or 'provisioning'
    if matching:
        matching[0]['name'] = name
    else:
        interfaces.append(dict(name=name, mac_address=mac))
    boot['pxe_interface'] = mac
    inventory.update(boot=boot, interfaces=interfaces,
                     _synthetic_port_name=not actual_name and not settings.get('provisioning_interface'))
    print(node['uuid']+': provisioning MAC from registered Ironic port', flush=True)
    return dict(record, inventory=inventory)


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
    port = boot_port(record, settings.get('provisioning_interface'))
    if inventory.get('_synthetic_port_name'):
        port['synthetic_name'] = True
    # SMBIOS system_vendor.serial_number is not proof of FRU Product Serial.
    # A controller IPMI FRU read remains the default, independent of Linux/SSH.
    identity = fru_identity(probe(node, inventory), str(settings.get('system_fru_id', '0')))
    observed = inventory.get('system_vendor', {}).get('serial_number')
    if observed and physical_serial(observed) != identity['serial']:
        raise ValueError('Inspection serial conflicts with verified FRU Product Serial')
    bmc = bmc_address(node, inventory)
    return dict(uuid=node['uuid'], serial=identity['serial'], name=identity['serial'],
                manufacturer=identity.get('manufacturer'), model=identity.get('model'),
                bmc=bmc, port=port)


def remote_fru(node, inventory):
    """Read the selected BMC without credentials in argv or output diagnostics."""
    from hwmanage_lib.common import Error, run
    from hwmanage_lib.ironic import credentials
    driver = credentials(node)
    address = bmc_address(dict(node, driver_info=driver), inventory)
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
    by_name = unique(sync.list('dcim/devices/', name=item['name']))
    matches = [d for d in (by_serial, by_name) if d]
    if len({d['id'] for d in matches}) > 1:
        raise ValueError('Serial and default name identify different NetBox devices')
    old = matches[0] if matches else None
    if old and old.get('serial') != serial:
        raise ValueError('Existing device has a conflicting serial')
    return old


def new_device_defaults(sync, settings):
    resolved = {}
    for key, path, field in [('site', 'dcim/sites/', 'name'),
                             ('role', 'dcim/device-roles/', 'name'),
                             ('device_type', 'dcim/device-types/', 'model')]:
        value = settings.get(key)
        if type(value) is int and value > 0:
            resolved[key] = value  # Compatibility with existing numeric settings.
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError('New devices require a NetBox name or slug for '+key)
        matches = {}
        for attribute in (field, 'slug'):
            for row in sync.list(path, **{attribute: value}):
                if row.get(attribute) == value:
                    matches[row['id']] = row
        if len(matches) != 1:
            reason = 'not found' if not matches else 'ambiguous; use a unique slug'
            raise ValueError('NetBox '+key+' '+repr(value)+' '+reason)
        resolved[key] = next(iter(matches))
    return resolved


def apply(sync, item, settings):
    from fhs_netbox import scalar
    old = resolve_device(sync, item)
    # Validate configuration/ownership before any write, including on repeated import.
    defaults = new_device_defaults(sync, settings) if not old else None
    ports = sync.list('dcim/interfaces/', device_id=old['id']) if old else []
    tagged = [p for p in ports if any(t.get('slug') == 'provisioning-interface' for t in p.get('tags', []))]
    if item['port'].get('synthetic_name'):
        matching = [p for p in ports if ((p.get('primary_mac_address') or {}).get('mac_address') or p.get('mac_address') or '').lower() == item['port']['mac']]
        if len(matching) > 1:
            raise ValueError('Provisioning MAC matches multiple existing NetBox interfaces')
        prior = matching or (tagged if len(tagged) == 1 else [])
        if prior:
            item = dict(item, port=dict(item['port'], name=prior[0]['name']))
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
    if old:
        # Do not change name, status, primary IP, tags, role or deployment context.
        data = {}
        key = {'id': old['id']}
    else:
        data = dict(defaults)
        data.update(name=item['name'], serial=item['serial'], status='planned')
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


class ImportFailures(RuntimeError):
    def __init__(self, results, failures):
        self.results = results
        self.failures = failures
        super().__init__(f'{len(results)} node(s) completed; {len(failures)} node(s) failed: '+', '.join(failures))


def import_nodes(nodes, ironic, settings, sync, probe=remote_fru):
    from collections import Counter
    items, failures, results = [], [], []

    def failed(uuid):
        failures.append(uuid)
        print(uuid+': FAILED', file=sys.stderr, flush=True)
        traceback.print_exc()

    for node in nodes.values():
        uuid = node['uuid']
        print(uuid+': reading inspection and verifying identity', flush=True)
        try:
            items.append(observation(node, saved_or_minimal_record(node, ironic, settings), settings, probe))
        except Exception:
            failed(uuid)
    # Check the whole observed batch before writes; reject every duplicate owner.
    counts = {key: Counter(item[key] for item in items) for key in ('serial', 'bmc')}
    ready = []
    for item in items:
        try:
            if any(counts[key][item[key]] > 1 for key in counts):
                raise ValueError('Selected discoveries contain duplicate chassis identities')
            resolve_device(sync, item)
            ironic.ensure_name(nodes[item['uuid']], item['serial'], plan=True)
            ready.append(item)
        except Exception:
            failed(item['uuid'])
    for item in ready:
        try:
            device = apply(sync, item, settings)
            ironic.ensure_name(nodes[item['uuid']], item['serial'], plan=sync.check)
            results.append(device)
            print(item['uuid']+': completed', flush=True)
        except Exception:
            failed(item['uuid'])
    if failures:
        raise ImportFailures(results, failures)
    return results


def import_selected(nodes, ironic, *, plan=False):
    """Shared import service for the optional wrapper and standalone entry point."""
    from fhs_netbox import Sync
    from hwmanage_lib.inventory import netbox_api
    api = netbox_api()
    from hwmanage_lib.settings import load, import_settings
    settings = import_settings(load()[1])
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
    parser.add_argument('--config', help='Controller YAML file')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Show remote application output')
    parser.add_argument('--plan', action='store_true', help='Validate without NetBox writes')
    args = parser.parse_args(argv)
    if args.verbose:
        os.environ["HWMANAGE_VERBOSE"] = str(args.verbose)
    sys.path.insert(0, str(HERE.parents[1]/'scripts/hwmanage'))
    from hwmanage_lib.common import Error
    from hwmanage_lib.ironic import Ironic
    from hwmanage_lib.settings import activated
    try:
        with activated(args.config):
            return execute(args, Ironic)
    except Exception:
        traceback.print_exc()
        return 1


def execute(args, Ironic):
    from hwmanage_lib.common import Error
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
    except ImportFailures as error:
        print(str(error), file=sys.stderr)
    except Error as error:
        print(str(error), file=sys.stderr)
    except Exception:
        traceback.print_exc()
    return 1


if __name__ == '__main__':
    sys.exit(main())
