"""Observed pluggable Inventory item metadata, separate from its parent card."""
import hashlib
import re
from ansible.module_utils.fhs_netbox import scalar, ensure_manufacturers, ensure_asset, asset_candidate


def port_inventory(sync, device, connector, vendor, part, serial, detail, interface):
    did = device['id']; name = connector+' transceiver'
    old = sync.find('dcim/inventory-items/', device_id=did, name=name)
    if old and old.get('serial') and serial and old['serial'] != serial:
        raise ValueError(name+': existing module identity differs; explicit replacement review required')
    if not interface: raise ValueError(name+': observed physical interface absent')
    if old and old.get('component_id') and (old['component_id'] != interface['id'] or old.get('component_type') != 'dcim.interface'):
        raise ValueError(name+': existing component association conflicts')
    maker = ensure_manufacturers(sync, [vendor])[vendor]
    previous = ((old or {}).get('custom_fields') or {}).get('fhs_module_observation') or {}
    detail['reported'] = dict(previous.get('reported') or {}, **detail['reported'])
    data = dict(device=did, name=name, manufacturer=maker['id'], part_id=part,
                component_type='dcim.interface', component_id=interface['id'],
                custom_fields=dict(fhs_module_observation=detail))
    if serial: data['serial'] = serial
    if old and scalar(old.get('manufacturer')) not in (None, maker['id']):
        raise ValueError(name+': existing manufacturer conflicts')
    if old and old.get('part_id') and old['part_id'] != part: raise ValueError(name+': existing part conflicts')
    itype = None
    if serial:
        slug = re.sub('[^a-z0-9]+', '-', part.lower()).strip('-')[:80]+'-'+hashlib.sha256(part.encode()).hexdigest()[:8]
        itype = sync.ensure('plugins/inventory/inventory-item-types/', dict(manufacturer_id=maker['id'], model=part),
                           dict(manufacturer=maker['id'], model=part, slug=slug, part_number=part), part+' inventory type')
        asset_candidate(sync, 'inventoryitem', itype['id'], serial, old['id'] if old else None)
    item = sync.ensure('dcim/inventory-items/', dict(device_id=did, name=name), data, name)
    if serial: ensure_asset(sync, 'inventoryitem', itype['id'], serial, item, name)
