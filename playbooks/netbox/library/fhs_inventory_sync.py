#!/usr/bin/python
"""Serial-safe chassis, component and Nexus asset reconciliation."""
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.fhs_netbox import (Sync, scalar, ensure_manufacturers,
    physical_serial, physical_device, observed_installation)
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


def server_type(sync, manufacturer, model):
    maker = sync.find('dcim/manufacturers/', name=manufacturer)
    if not maker:
        raise ValueError('Create manufacturer before chassis reconciliation')
    key = {'manufacturer_id': maker['id'], 'model': model}
    dtype = sync.find('dcim/device-types/', **key)
    if dtype:
        return dtype
    slug = re.sub('[^a-z0-9]+', '-', model.lower()).strip('-')[:80] or 'server'
    slug += '-' + hashlib.sha256((manufacturer + '\0' + model).encode()).hexdigest()[:8]
    return sync.ensure('dcim/device-types/', key,
                       {'manufacturer': maker['id'], 'model': model, 'slug': slug, 'u_height': 0},
                       model + ' device type')


def synchronize(params,check):
    sync=Sync(params,check)
    mode=params['mode']; name=params['device']
    if mode=='device':
        serial=str(params.get('serial') or '').strip()
        device=physical_device(sync,name,serial,params.get('allow_missing_serial',False))
        if not device and not serial: return sync.plan
        previous=(device or {}).get('device_type') or {}
        if not isinstance(previous,dict): previous={}
        manufacturer=params.get('manufacturer') or (previous.get('manufacturer') or {}).get('name') or 'NA'
        model=params.get('model') or previous.get('model') or 'Unknown'
        ensure_manufacturers(sync,[manufacturer])
        dtype=server_type(sync,manufacturer,model)
        data={'name':name,'device_type':dtype['id']}
        old_site=(device or {}).get('site') or {}
        if not isinstance(old_site,dict): old_site=sync.find('dcim/sites/',id=old_site) or {}
        site_name=params.get('site') or old_site.get('name') or 'MDA'
        site=sync.ensure('dcim/sites/',{'name':site_name},{'name':site_name,'slug':re.sub('[^a-z0-9]+','-',site_name.lower()).strip('-')},site_name)
        data['site']=site['id']
        role_name=params.get('role') or (None if device else 'Unassigned')
        if role_name:
            role=sync.ensure('dcim/device-roles/',{'name':role_name},
                {'name':role_name,'slug':re.sub('[^a-z0-9]+','-',role_name.lower()).strip('-')},role_name)
            data['role']=role['id']
        if not device: data['status']='active'
        if params.get('category'):
            tag=params['category']
            record=sync.ensure('extras/tags/',{'slug':tag},{'name':tag,'slug':tag},tag)
            data['tags']=[scalar(t) for t in (device or {}).get('tags',[]) if scalar(t)!=record['id']]+[record['id']]
        key={'id':device['id']} if device else {'name':name}
        installed_serial=serial
        if not installed_serial and device:
            try: installed_serial=physical_serial(device.get('serial'))
            except ValueError: pass
        if installed_serial:
            data['serial']=installed_serial
            observed_installation(sync,'device','dcim/devices/',key,data,dtype['id'],name)
        elif device:
            sync.ensure('dcim/devices/',key,data,name)
        else:
            raise ValueError('No device serial; chassis not created')
        return sync.plan
    device=sync.find('dcim/devices/',name=name)
    if not device: raise ValueError('Create parent device before importing components')
    did=device['id']
    for item in params.get('items',[]):
        if not item.get('serial'): continue
        maker_name=item.get('manufacturer') or params.get('manufacturer') or 'NA'
        maker=ensure_manufacturers(sync,[maker_name])[maker_name]
        model=item.get('model') or item.get('part') or 'Unknown'
        if mode=='nexus':
            dtype=sync.ensure('dcim/module-types/',{'manufacturer_id':maker['id'],'model':model},
                {'manufacturer':maker['id'],'model':model,'part_number':item.get('part') or model},model)
            bay=sync.ensure('dcim/module-bays/',{'device_id':did,'name':item['bay']},
                {'device':did,'name':item['bay']},item['bay'])
            key={'device_id':did,'module_bay_id':bay['id']}
            data={'device':did,'module_bay':bay['id'],'module_type':dtype['id'],'serial':item['serial'],'status':'active'}
            if item.get('description'): data['description']=item['description']
            observed_installation(sync,'module','dcim/modules/',key,data,dtype['id'],item['bay'])
        else:
            dtype=item_type(sync,maker['id'],model,item.get('part'))
            key={'device_id':did,'name':item['name']}
            data={'device':did,'name':item['name'],'manufacturer':maker['id'],'serial':item['serial']}
            if item.get('part'): data['part_id']=item['part']
            observed_installation(sync,'inventoryitem','dcim/inventory-items/',key,data,dtype['id'],item['name'])
    # An absent observation is never a removal request, including legacy complete flags.
    return sync.plan


def main():
    module=AnsibleModule(argument_spec=dict(
        netbox_url=dict(required=True),netbox_token=dict(required=True,no_log=True),
        validate_certs=dict(type='bool',default=True),device=dict(required=True),
        mode=dict(required=True,choices=['resolve','type','device','components','nexus']),
        allow_missing_serial=dict(type='bool',default=False),
        serial=dict(default=''),manufacturer=dict(default='Unknown'),model=dict(default=''),
        site=dict(default=''),role=dict(default=''),items=dict(type='list',elements='dict',default=[]),
        complete=dict(type='bool',default=False),scope=dict(type='list',elements='str',default=[]),
        identity_sources=dict(type='dict',default={}),category=dict(default=''),
        preview=dict(type='bool',default=False)),supports_check_mode=True)
    try:
        if module.params['mode']=='type':
            sync=Sync(module.params,module.check_mode or module.params['preview'])
            dtype=server_type(sync,module.params['manufacturer'],module.params['model'])
            module.exit_json(changed=bool(sync.plan),plan=sync.plan,device_type=dtype)
        if module.params['mode']=='resolve':
            device=physical_device(Sync(module.params,True),module.params['device'],module.params['serial'],module.params['allow_missing_serial'])
            module.exit_json(changed=False,device=device)
        plan=synchronize(module.params,module.check_mode or module.params['preview'])
        module.exit_json(changed=bool(plan),plan=plan)
    except Exception as error:
        module.fail_json(msg=str(error) if isinstance(error,ValueError) else 'Inventory reconciliation failed; inspect NetBox state and journals before retrying')


if __name__=='__main__': main()
