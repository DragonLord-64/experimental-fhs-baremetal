#!/usr/bin/python
"""Validate all placement/power identities before changing these records."""
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.fhs_netbox import Sync, scalar, physical_device


def synchronize(params, check):
    sync = Sync(params, check); meta = params['metadata']; name = params['device']; diagnostics = []
    if not any(k in meta for k in ('rack_unit', 'power_ports')): return dict(plan=[], diagnostics=['No new placement/power metadata; existing records preserved'])
    device = physical_device(sync, name, params.get('serial', ''), allow_missing=True)
    did = device['id'] if device else None
    placement = None; power = []
    if 'rack_unit' in meta:
        unit = meta['rack_unit']
        if not isinstance(unit, int) or isinstance(unit, bool) or unit < 1: raise ValueError('rack_unit must be a positive integer')
        site = sync.find('dcim/sites/', name=meta.get('site', ''))
        rack = sync.find('dcim/racks/', site_id=site['id'], name=meta.get('rack', '')) if site else None
        if not rack:
            if not check: raise ValueError('rack_unit target rack is missing; import site/rack first')
            diagnostics.append('rack_unit validation deferred until target rack exists; preview makes no placement claim')
        else:
            if device and scalar(device.get('rack')) not in (None, rack['id']):
                raise ValueError('rack_unit conflicts with existing rack assignment')
            dtype = (device or {}).get('device_type') or {}
            if dtype and not isinstance(dtype, dict): dtype = sync.find('dcim/device-types/', id=dtype) or {}
            height = dtype.get('u_height')
            if height is None and dtype.get('id'):
                dtype = sync.find('dcim/device-types/', id=dtype['id']) or {}
                height = dtype.get('u_height')
            if height is None and params.get('model') and params.get('manufacturer'):
                maker = sync.find('dcim/manufacturers/', name=params['manufacturer'])
                dtype = sync.find('dcim/device-types/', manufacturer_id=maker['id'], model=params['model']) if maker else None
                height = (dtype or {}).get('u_height')
            if not device and height is None and check:
                diagnostics.append('rack_unit device-height validation deferred until verified device type exists')
            else:
                if height is None or float(height) <= 0: raise ValueError('rack_unit requires a rack-mounted device type with known positive height')
                top = float(unit)+float(height)
                if top > float(rack['u_height'])+1: raise ValueError('rack_unit exceeds rack height')
                if device and device.get('position') is not None and float(device['position']) != unit:
                    raise ValueError('rack_unit conflicts with existing device position')
                # Conservatively reserve both faces. Do not guess the placement of
                # another device from an absent face or half-depth report.
                for occupant in sync.list('dcim/devices/', rack_id=rack['id']):
                    if occupant['id'] == did or occupant.get('position') is None: continue
                    otype = occupant.get('device_type') or {}; oh = otype.get('u_height') if isinstance(otype, dict) else None
                    if oh is None:
                        otype = sync.find('dcim/device-types/', id=scalar(otype)); oh = (otype or {}).get('u_height')
                    if oh is None: raise ValueError('Existing rack occupant has unknown height; cannot validate placement')
                    start = float(occupant['position']); end = start+float(oh)
                    if not (top <= start or unit >= end): raise ValueError('rack_unit overlaps an existing device')
                face = scalar((device or {}).get('face')) or params.get('default_face', 'front')
                placement = dict(rack=rack['id'], position=unit, face=face)
    inlets = meta.get('power_ports', [])
    if not isinstance(inlets, list): raise ValueError('power_ports must be a list')
    names = set(); outlets = set()
    for mapping in inlets:
        if set(mapping) != {'name', 'pdu_serial', 'pdu_port'} or any(not isinstance(v, str) or not v.strip() for v in mapping.values()):
            raise ValueError('Power mapping requires exact nonempty string name, pdu_serial and pdu_port')
        inlet_name = mapping['name']; identity = (mapping['pdu_serial'], mapping['pdu_port'])
        if inlet_name in names or identity in outlets: raise ValueError('Duplicate power inlet or outlet')
        names.add(inlet_name); outlets.add(identity)
        pdus = sync.list('dcim/devices/', serial=mapping['pdu_serial'])
        pdus = [p for p in pdus if p.get('serial') == mapping['pdu_serial']]
        if len(pdus) != 1: raise ValueError(inlet_name+': PDU serial missing or ambiguous')
        if pdus[0]['id'] == did: raise ValueError(inlet_name+': PDU identity is the server itself')
        rows = sync.list('dcim/power-outlets/', device_id=pdus[0]['id'], name=mapping['pdu_port'])
        rows = [p for p in rows if p['name'] == mapping['pdu_port'] and scalar(p.get('device')) == pdus[0]['id']]
        if len(rows) != 1: raise ValueError(inlet_name+': PDU outlet name missing or ambiguous')
        outlet = rows[0]
        inlet = sync.find('dcim/power-ports/', device_id=did, name=inlet_name) if did else None
        ac = scalar((inlet or {}).get('cable')); bc = scalar(outlet.get('cable'))
        if ac or bc:
            same = False
            if inlet and ac and ac == bc:
                cable = sync.request('GET', f'dcim/cables/{ac}/')
                terms = cable.get('a_terminations', [])+cable.get('b_terminations', [])
                same = len(terms) == 2 and {(t['object_type'], t['object_id']) for t in terms} == {('dcim.powerport', inlet['id']), ('dcim.poweroutlet', outlet['id'])}
            if same:
                diagnostics.append(inlet_name+': expected power cable already present'); continue
            raise ValueError(inlet_name+': occupied power termination; existing cable preserved')
        if outlet.get('mark_connected') or (inlet or {}).get('mark_connected'):
            raise ValueError(inlet_name+': power termination marked occupied')
        power.append((inlet_name, inlet, outlet))
    # All identities/conflicts above are validated before the first mutation.
    if not device:
        if check: return dict(plan=[], diagnostics=diagnostics+['Parent server not yet imported; power identities validated; creation deferred'])
        raise ValueError('Import parent server before applying placement/power')
    if placement: sync.ensure('dcim/devices/', dict(id=did), placement, name+' rack position')
    for inlet_name, inlet, outlet in power:
        if not inlet:
            inlet = sync.ensure('dcim/power-ports/', dict(device_id=did, name=inlet_name), dict(device=did, name=inlet_name), inlet_name)
        data = dict(a_terminations=[dict(object_type='dcim.powerport', object_id=inlet['id'])],
                    b_terminations=[dict(object_type='dcim.poweroutlet', object_id=outlet['id'])], status='connected', description='FHS server-info explicit power mapping')
        sync.plan.append(dict(object=inlet_name+' cable', action='create', before={}, after=data))
        if not check: sync.request('POST', 'dcim/cables/', json=data)
    return dict(plan=sync.plan, diagnostics=diagnostics)


def main():
    module = AnsibleModule(argument_spec=dict(netbox_url=dict(required=True), netbox_token=dict(required=True, no_log=True),
        validate_certs=dict(type='bool', default=True), device=dict(required=True), metadata=dict(type='dict', required=True),
        manufacturer=dict(default=''), model=dict(default=''), serial=dict(default=''), default_face=dict(default='front', choices=['front', 'rear']),
        preview=dict(type='bool', default=False)), supports_check_mode=True)
    try:
        result = synchronize(module.params, module.check_mode or module.params['preview'])
        module.exit_json(changed=bool(result['plan']), **result)
    except Exception as error:
        module.fail_json(msg=str(error) if isinstance(error, ValueError) else 'Placement/power reconciliation failed; inspect private diagnostics')


if __name__ == '__main__': main()
