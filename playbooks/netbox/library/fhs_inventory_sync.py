#!/usr/bin/python
"""Serial-safe chassis, component and Nexus asset reconciliation."""
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.fhs_netbox import (Sync, scalar, ensure_manufacturers,
    physical_serial, physical_device, asset_candidate, ensure_asset, retire_module)
import hashlib
import re


def item_type(sync,maker,model,part_number=None):
    slug=re.sub('[^a-z0-9]+','-',model.lower()).strip('-')[:80] or 'component'
    slug+='-'+hashlib.sha256(model.encode()).hexdigest()[:8]
    data={'manufacturer':maker,'model':model,'slug':slug}
    if part_number: data['part_number']=part_number
    return sync.ensure('plugins/inventory/inventory-item-types/',
        {'manufacturer_id':maker,'model':model},
        data,model+' inventory type')


def synchronize(params,check):
    sync=Sync(params,check)
    mode=params['mode']; name=params['device']
    if mode=='device':
        serial=str(params.get('serial') or '').strip()
        optional=params.get('allow_missing_serial',False)
        if serial or not optional: serial=physical_serial(serial)
        maker=sync.find('dcim/manufacturers/',name=params['manufacturer'])
        if not maker: raise ValueError('Create manufacturer before chassis reconciliation')
        dtype=sync.find('dcim/device-types/',manufacturer_id=maker['id'],model=params['model'])
        if not dtype: raise ValueError('Create device type before chassis reconciliation')
        device=physical_device(sync,name,serial,optional)
        if device and scalar(device['device_type'])!=dtype['id']:
            raise ValueError('Chassis model differs; review identity before applying')
        if serial: asset_candidate(sync,'device',dtype['id'],serial,device['id'] if device else None)
        data={'name':name,'device_type':dtype['id']}
        if serial: data['serial']=serial
        if not device:
            site=sync.find('dcim/sites/',name=params['site'])
            role=sync.find('dcim/device-roles/',name=params['role'])
            if not site or not role: raise ValueError('Create site and role before chassis reconciliation')
            data.update(site=site['id'],role=role['id'],status='active')
        key={'id':device['id']} if device else {'name':name}
        device=sync.ensure('dcim/devices/',key,data,name+' chassis')
        if serial: ensure_asset(sync,'device',dtype['id'],serial,device,name)
        return sync.plan
    device=sync.find('dcim/devices/',name=name)
    if not device: raise ValueError('Create parent device before asset reconciliation')
    did=device['id']; items=params.get('items',[])
    names=[v.get('bay') if mode=='nexus' else v.get('name') for v in items]
    serials=[physical_serial(v.get('serial')) for v in items]
    if len(names)!=len(set(names)) or len(serials)!=len(set(serials)):
        raise ValueError('Duplicate component bay/name or serial; preserve inventory')
    if mode=='nexus':
        for item in items:
            maker=ensure_manufacturers(sync,[item['manufacturer']])[item['manufacturer']]
            mtype=sync.ensure('dcim/module-types/',{'manufacturer_id':maker['id'],'model':item['model']},
                {'manufacturer':maker['id'],'model':item['model'],'part_number':item['model']},item['model']+' type')
            bay=sync.ensure('dcim/module-bays/',{'device_id':did,'name':item['bay']},
                {'device':did,'name':item['bay']},item['bay'])
            key={'device_id':did,'module_bay_id':bay['id']}
            old=sync.find('dcim/modules/',**key); serial=physical_serial(item['serial'])
            asset_candidate(sync,'module',mtype['id'],serial,old['id'] if old and old.get('serial')==serial else None)
            replacement=old and old.get('serial')!=serial
            previous=old.get('serial') if replacement else None
            if replacement: retire_module(sync,did,item['bay'],old,serial)
            try:
                installed=sync.ensure('dcim/modules/',key,
                    {'device':did,'module_bay':bay['id'],'module_type':mtype['id'],'serial':serial,'status':'active',
                     'description':item.get('description','')},item['bay']+' module')
                ensure_asset(sync,'module',mtype['id'],serial,installed,item['bay'])
                if replacement: sync.journal(did,item['bay'],previous,serial,'installed',cabling='unverified; no cable copied')
            except Exception:
                if replacement: sync.journal(did,item['bay'],previous,serial,'failed',cabling='unverified; inspect partial installation')
                raise
        # Only exact caller-supplied bays may reconcile absence, never every bay.
        if params.get('complete'):
            for bay_name in params.get('scope',[]):
                if bay_name in names: continue
                bay=sync.find('dcim/module-bays/',device_id=did,name=bay_name)
                old=sync.find('dcim/modules/',device_id=did,module_bay_id=bay['id']) if bay else None
                if old: retire_module(sync,did,bay_name,old)
        return sync.plan
    maker=ensure_manufacturers(sync,[params['manufacturer']])[params['manufacturer']]
    for item in items:
        item_maker=item.get('manufacturer') or params['manufacturer']
        maker=ensure_manufacturers(sync,[item_maker])[item_maker]
        serial=physical_serial(item['serial']); model=str(item.get('model') or item.get('part') or '').strip()
        part=str(item.get('part') or '').strip()
        if not model: raise ValueError('Component model/part missing; preserve existing inventory')
        kind=item.get('kind','Component')
        itype=item_type(sync,maker['id'],model,part)
        key={'device_id':did,'name':item['name']}
        old=sync.find('dcim/inventory-items/',**key)
        asset_candidate(sync,'inventoryitem',itype['id'],serial,old['id'] if old and old.get('serial')==serial else None)
        replacement=old and old.get('serial')!=serial
        previous=old.get('serial') if replacement else None
        if replacement:
            old_serial=physical_serial(old.get('serial'))
            assigned=sync.find('plugins/inventory/assets/',inventoryitem_id=old['id'])
            if not assigned:
                old_type=item_type(sync,scalar(old.get('manufacturer')) or maker['id'],old.get('part_id',''))
                ensure_asset(sync,'inventoryitem',old_type['id'],old_serial,old,item['name'])
            if any(scalar(v.get('parent'))==old['id'] for v in sync.list('dcim/inventory-items/',device_id=did)):
                raise ValueError('Component has child inventory; review before replacement')
            sync.journal(did,item['name'],old_serial,serial,'started',cabling='not mapped')
            sync.delete('dcim/inventory-items/',old,item['name']+' installation')
        try:
            data={'device':did,'name':item['name'],'manufacturer':maker['id'],'serial':serial,
                  'description':old.get('description') if old and not replacement and old.get('description') else 'FHS managed '+kind}
            if part: data['part_id']=part
            installed=sync.ensure('dcim/inventory-items/',key,data,item['name']+' component')
            ensure_asset(sync,'inventoryitem',itype['id'],serial,installed,item['name'])
            if replacement: sync.journal(did,item['name'],previous,serial,'installed',cabling='not mapped')
        except Exception:
            if replacement: sync.journal(did,item['name'],previous,serial,'failed',cabling='not mapped; inspect partial installation')
            raise
    if params.get('complete'):
        for old in sync.list('dcim/inventory-items/',device_id=did):
            if old['name'] in names or old.get('description') not in ['FHS managed '+kind for kind in params.get('scope',[])]: continue
            physical_serial(old.get('serial'))
            assigned=sync.find('plugins/inventory/assets/',inventoryitem_id=old['id'])
            if not assigned: raise ValueError('Untracked old component needs asset adoption before removal')
            if any(scalar(v.get('parent'))==old['id'] for v in sync.list('dcim/inventory-items/',device_id=did)):
                raise ValueError('Component has child inventory; review before removal')
            sync.journal(did,old['name'],old['serial'],None,'started',cabling='not mapped')
            sync.delete('dcim/inventory-items/',old,old['name']+' installation')
            sync.journal(did,old['name'],old['serial'],None,'removed',cabling='not mapped')
    return sync.plan


def main():
    module=AnsibleModule(argument_spec=dict(
        netbox_url=dict(required=True),netbox_token=dict(required=True,no_log=True),
        validate_certs=dict(type='bool',default=True),device=dict(required=True),
        mode=dict(required=True,choices=['resolve','device','components','nexus']),
        allow_missing_serial=dict(type='bool',default=False),
        serial=dict(default=''),manufacturer=dict(default='Unknown'),model=dict(default=''),
        site=dict(default=''),role=dict(default=''),items=dict(type='list',elements='dict',default=[]),
        complete=dict(type='bool',default=False),scope=dict(type='list',elements='str',default=[]),
        preview=dict(type='bool',default=False)),supports_check_mode=True)
    try:
        if module.params['mode']=='resolve':
            device=physical_device(Sync(module.params,True),module.params['device'],module.params['serial'],module.params['allow_missing_serial'])
            module.exit_json(changed=False,device=device)
        plan=synchronize(module.params,module.check_mode or module.params['preview'])
        module.exit_json(changed=bool(plan),plan=plan)
    except Exception as error:
        module.fail_json(msg=str(error) if isinstance(error,ValueError) else 'Inventory reconciliation failed; inspect NetBox state and journals before retrying')


if __name__=='__main__': main()
