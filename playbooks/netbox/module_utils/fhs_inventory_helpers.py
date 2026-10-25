"""Observed pluggable Inventory item metadata, separate from its parent card."""
import hashlib
import re
from ansible.module_utils.fhs_netbox import scalar, ensure_manufacturers, observed_installation


def port_inventory(sync, device, connector, vendor, part, serial, detail, interface):
    did = device['id']; name = connector+' transceiver'
    old = sync.find('dcim/inventory-items/', device_id=did, name=name)
    if not interface: raise ValueError(name+': observed physical interface absent')
    maker = ensure_manufacturers(sync, [vendor])[vendor]
    previous = ((old or {}).get('custom_fields') or {}).get('fhs_module_observation') or {}
    detail['reported'] = dict(previous.get('reported') or {}, **detail['reported'])
    data = dict(device=did, name=name, manufacturer=maker['id'], part_id=part,
                component_type='dcim.interface', component_id=interface['id'],
                custom_fields=dict(fhs_module_observation=detail))
    if serial: data['serial'] = serial
    itype = None
    if serial:
        slug = re.sub('[^a-z0-9]+', '-', part.lower()).strip('-')[:80]+'-'+hashlib.sha256(part.encode()).hexdigest()[:8]
        itype = sync.ensure('plugins/inventory/inventory-item-types/', dict(manufacturer_id=maker['id'], model=part),
                           dict(manufacturer=maker['id'], model=part, slug=slug, part_number=part), part+' inventory type')
    key = dict(device_id=did, name=name)
    if serial: observed_installation(sync, 'inventoryitem', 'dcim/inventory-items/', key, data, itype['id'], name)
    else: sync.ensure('dcim/inventory-items/', key, data, name)
