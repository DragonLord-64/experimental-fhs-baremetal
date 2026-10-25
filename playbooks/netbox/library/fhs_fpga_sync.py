#!/usr/bin/python
"""Reconcile FPGA/NIC modules and adopt interfaces in place."""
from ansible.module_utils.basic import AnsibleModule
import re
import requests


from ansible.module_utils.fhs_netbox import Sync, scalar, ensure_manufacturers, physical_serial, asset_candidate, ensure_asset, retire_module


def synchronize(params,check):
    sync=Sync(params,check)
    kind=params.get('kind','FPGA')
    manufacturer=(params.get('manufacturer') or ('Mellanox' if kind=='NIC' else 'BittWare')).strip()
    if not params['cards'] and not params.get('complete',False):return sync.plan
    device=sync.find('dcim/devices/',name=params['device'])
    if device is None and not check:raise ValueError('Create the parent server before applying hardware modules')
    device_id=device['id'] if device else -1
    cards=[dict(card) for card in params['cards']]
    serials=[]; bays=[]
    for card in cards:
        card['serial']=physical_serial(card.get('serial'))
        serials.append(card['serial']); bays.append(card['bay'])
        card.setdefault('interfaces',[])
    if len(serials)!=len(set(serials)) or len(bays)!=len(set(bays)):
        raise ValueError('Duplicate physical card serials or bays; preserve existing inventory')
    if not cards:
        for bay in sync.list('dcim/module-bays/',device_id=device_id):
            if not bay['name'].startswith(kind+' '): continue
            existing=sync.find('dcim/modules/',device_id=device_id,module_bay_id=bay['id'])
            if existing: retire_module(sync,device_id,bay['name'],existing)
        return sync.plan
    if kind=='NIC':
        for card in cards:
            previous=sync.find('dcim/modules/',device_id=device_id,serial=card['serial'])
            if previous:
                old_type=sync.find('dcim/module-types/',id=scalar(previous['module_type']))
                old_bay=sync.find('dcim/module-bays/',id=scalar(previous['module_bay']))
                if old_type and old_type['model']==card['part'] and old_bay and old_bay['name'].startswith('NIC '):
                    card['bay']=old_bay['name'];card['position']=old_bay.get('position',card['position'])
    for card in cards:
        existing_bay=sync.find('dcim/module-bays/',device_id=device_id,name=card['bay'])
        existing=sync.find('dcim/modules/',device_id=device_id,module_bay_id=existing_bay['id']) if existing_bay else None
        for interface in card['interfaces']:
            old=sync.find('dcim/interfaces/',device_id=device_id,name=interface['name'])
            if old and old.get('module') and (not existing or scalar(old['module'])!=existing['id']):
                raise ValueError('Interface '+interface['name']+' already belongs to another module')
    maker=ensure_manufacturers(sync,[manufacturer])[manufacturer]
    definitions=[('fpga_bmc_firmware','text'),('fpga_board_version','text'),('pci_endpoints','json')] if kind=='FPGA' else [('nic_driver','text'),('nic_firmware','text'),('nic_functions','json'),('pci_endpoints','json')]
    for name,field_kind in definitions:
        old=sync.find('extras/custom-fields/',name=name)
        if old and scalar(old['type'])!=field_kind:raise ValueError('Incompatible existing custom field '+name)
        types=list((old or {}).get('object_types') or [])
        if 'dcim.module' not in types:types.append('dcim.module')
        sync.ensure('extras/custom-fields/',{'name':name},{'name':name,'type':field_kind,'object_types':types},name+' field')
    staging_model='FHS '+kind+' staging (no components)'
    staging=sync.ensure('dcim/module-types/',{'manufacturer_id':maker['id'],'model':staging_model},
                        {'manufacturer':maker['id'],'model':staging_model},'template-free staging type')
    if staging['id']>0:
        for endpoint in ['interface-templates','power-port-templates','power-outlet-templates','console-port-templates','console-server-port-templates','front-port-templates','rear-port-templates','module-bay-templates']:
            found=sync.request('GET','dcim/'+endpoint+'/',params={'module_type_id':staging['id'],'limit':1})
            if found['count']:raise ValueError('Staging module type must not have component templates')
    for card in cards:
        module_type=sync.ensure('dcim/module-types/',{'manufacturer_id':maker['id'],'model':card['part']},
                                {'manufacturer':maker['id'],'model':card['part'],'part_number':card['part']},card['part']+' module type')
        bay=sync.ensure('dcim/module-bays/',{'device_id':device_id,'name':card['bay']},
                        {'device':device_id,'name':card['bay'],'position':card['position']},params['device']+' '+card['bay'])
        field_map=[('fpga_bmc_firmware','bmc_firmware'),('fpga_board_version','version'),('pci_endpoints','pci_endpoints')] if kind=='FPGA' else [('nic_driver','driver'),('nic_firmware','firmware'),('nic_functions','functions'),('pci_endpoints','pci_endpoints')]
        fields={k:card[v] for k,v in field_map if card.get(v)}
        key={'device_id':device_id,'module_bay_id':bay['id']}
        existing=sync.find('dcim/modules/',**key)
        asset_candidate(sync,'module',module_type['id'],card['serial'],existing['id'] if existing and existing.get('serial')==card['serial'] else None)
        replacement=existing and existing.get('serial')!=card['serial']
        old_serial=existing.get('serial') if replacement else None
        if replacement:
            retire_module(sync,device_id,card['bay'],existing,card['serial'])
            existing=None
        if kind=='NIC' and existing:
            previous=existing.get('custom_fields') or {}
            functions={(f['address'],f['interface']):dict(f) for f in previous.get('nic_functions') or []}
            for observation in fields.get('nic_functions',[]):
                identity=(observation['address'],observation['interface'])
                functions[identity]=dict(functions.get(identity,{}),**{k:v for k,v in observation.items() if v not in ['',None]})
            fields['nic_functions']=[functions[k] for k in sorted(functions)]
            for field,key_name in [('nic_driver','driver'),('nic_firmware','firmware')]:
                values=sorted({f[key_name] for f in functions.values() if f.get(key_name)})
                if values:fields[field]=', '.join(values)
            endpoints={p['address']:p for p in previous.get('pci_endpoints') or []}
            endpoints.update({p['address']:p for p in fields.get('pci_endpoints',[])})
            if endpoints:fields['pci_endpoints']=[endpoints[k] for k in sorted(endpoints)]
        try:
            if not existing:
                installed=sync.ensure('dcim/modules/',key,{'device':device_id,'module_bay':bay['id'],'module_type':staging['id'],'serial':card['serial'],'status':'active','custom_fields':fields},card['bay']+' module')
            else:installed=existing
            for interface in card['interfaces']:
                ikey={'device_id':device_id,'name':interface['name']}
                old=sync.find('dcim/interfaces/',**ikey)
                data={'device':device_id,'name':interface['name'],'module':installed['id']}
                if not old:data.update(type=interface['type'],enabled=True)
                sync.ensure('dcim/interfaces/',ikey,data,interface['name'])
            # Update model/telemetry only on the same physical serial; replacement
            # above always deletes/recreates the installed record first.
            installed=sync.ensure('dcim/modules/',key,{'device':device_id,'module_bay':bay['id'],'module_type':module_type['id'],'serial':card['serial'],'status':'active','custom_fields':fields},card['bay']+' identity')
            ensure_asset(sync,'module',module_type['id'],card['serial'],installed,card['bay'])
            if replacement: sync.journal(device_id,card['bay'],old_serial,card['serial'],'installed',module_id=installed['id'],cabling='unverified; no cable copied')
        except Exception:
            if replacement: sync.journal(device_id,card['bay'],old_serial,card['serial'],'failed',cabling='unverified; inspect partial installation')
            raise
    if params.get('complete',False):
        observed={card['bay'] for card in cards}
        for bay in sync.list('dcim/module-bays/',device_id=device_id):
            if not bay['name'].startswith(kind+' ') or bay['name'] in observed: continue
            existing=sync.find('dcim/modules/',device_id=device_id,module_bay_id=bay['id'])
            if existing: retire_module(sync,device_id,bay['name'],existing)
    return sync.plan


def main():
    module=AnsibleModule(argument_spec=dict(netbox_url=dict(required=True),netbox_token=dict(required=True,no_log=True),validate_certs=dict(type='bool',default=True),device=dict(required=True),cards=dict(type='list',elements='dict',required=True),preview=dict(type='bool',default=False),complete=dict(type='bool',default=False),kind=dict(default='FPGA',choices=['FPGA','NIC']),manufacturer=dict(default='')),supports_check_mode=True)
    try:
        plan=synchronize(module.params,module.check_mode or module.params['preview'])
        module.exit_json(changed=bool(plan),plan=plan,diff={'before':'Existing hardware module resources','after':plan} if module._diff else {})
    except Exception as error:
        module.fail_json(msg=str(error) if isinstance(error,ValueError) else 'Hardware module reconciliation failed; check NetBox connectivity and API permissions')


if __name__=='__main__':main()
