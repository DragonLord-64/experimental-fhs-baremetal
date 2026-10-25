#!/usr/bin/python
"""Reconcile FPGA/NIC modules and adopt interfaces in place."""
from ansible.module_utils.basic import AnsibleModule


from ansible.module_utils.fhs_netbox import Sync, scalar, ensure_manufacturers, physical_serial, observed_installation


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
    if not cards: return sync.plan
    if not params.get('write_modules',True):
        if not params.get('write_interfaces',True): return sync.plan
        for card in cards:
            installed=sync.find('dcim/modules/',device_id=device_id,serial=card['serial'])
            for interface in card['interfaces']:
                data={'device':device_id,'name':interface['name']}
                if installed: data['module']=installed['id']
                old=sync.find('dcim/interfaces/',device_id=device_id,name=interface['name'])
                if not old: data['type']=interface['type']
                sync.ensure('dcim/interfaces/',{'device_id':device_id,'name':interface['name']},data,interface['name'])
        return sync.plan
    if kind=='NIC':
        for card in cards:
            previous=sync.find('dcim/modules/',device_id=device_id,serial=card['serial'])
            if previous:
                old_type=sync.find('dcim/module-types/',id=scalar(previous['module_type']))
                old_bay=sync.find('dcim/module-bays/',id=scalar(previous['module_bay']))
                if old_type and old_type['model']==card['part'] and old_bay and old_bay['name'].startswith('NIC '):
                    card['bay']=old_bay['name'];card['position']=old_bay.get('position',card['position'])
    maker=ensure_manufacturers(sync,[manufacturer])[manufacturer]
    definitions=[('fpga_bmc_firmware','text'),('fpga_board_version','text'),('pci_endpoints','json')] if kind=='FPGA' else [('nic_driver','text'),('nic_firmware','text'),('nic_functions','json'),('pci_endpoints','json')]
    for name,field_kind in definitions:
        old=sync.find('extras/custom-fields/',name=name)
        if old and scalar(old['type'])!=field_kind:raise ValueError('Incompatible existing custom field '+name)
        types=list((old or {}).get('object_types') or [])
        if 'dcim.module' not in types:types.append('dcim.module')
        sync.ensure('extras/custom-fields/',{'name':name},{'name':name,'type':field_kind,'object_types':types},name+' field')
    for card in cards:
        module_type=sync.ensure('dcim/module-types/',{'manufacturer_id':maker['id'],'model':card['part']},
                                {'manufacturer':maker['id'],'model':card['part'],'part_number':card['part']},card['part']+' module type')
        bay=sync.ensure('dcim/module-bays/',{'device_id':device_id,'name':card['bay']},
                        {'device':device_id,'name':card['bay'],'position':card['position']},params['device']+' '+card['bay'])
        field_map=[('fpga_bmc_firmware','bmc_firmware'),('fpga_board_version','version'),('pci_endpoints','pci_endpoints')] if kind=='FPGA' else [('nic_driver','driver'),('nic_firmware','firmware'),('nic_functions','functions'),('pci_endpoints','pci_endpoints')]
        fields={k:card[v] for k,v in field_map if card.get(v)}
        key={'device_id':device_id,'module_bay_id':bay['id']}
        existing=sync.find('dcim/modules/',**key)
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
        installed=observed_installation(sync,'module','dcim/modules/',key,
            {'device':device_id,'module_bay':bay['id'],'module_type':module_type['id'],
             'serial':card['serial'],'status':'active','custom_fields':fields},module_type['id'],card['bay'])
        for interface in card['interfaces'] if params.get('write_interfaces',True) else []:
            ikey={'device_id':device_id,'name':interface['name']}
            old=sync.find('dcim/interfaces/',**ikey)
            data={'device':device_id,'name':interface['name'],'module':installed['id']}
            if not old: data.update(type=interface['type'],enabled=True)
            sync.ensure('dcim/interfaces/',ikey,data,interface['name'])
    # Never remove modules merely because discovery did not report them.
    return sync.plan


def main():
    module=AnsibleModule(argument_spec=dict(netbox_url=dict(required=True),netbox_token=dict(required=True,no_log=True),validate_certs=dict(type='bool',default=True),device=dict(required=True),cards=dict(type='list',elements='dict',required=True),preview=dict(type='bool',default=False),complete=dict(type='bool',default=False),kind=dict(default='FPGA',choices=['FPGA','NIC']),manufacturer=dict(default=''),write_modules=dict(type='bool',default=True),write_interfaces=dict(type='bool',default=True)),supports_check_mode=True)
    try:
        plan=synchronize(module.params,module.check_mode or module.params['preview'])
        module.exit_json(changed=bool(plan),plan=plan,diff={'before':'Existing hardware module resources','after':plan} if module._diff else {})
    except Exception as error:
        module.fail_json(msg=str(error) if isinstance(error,ValueError) else 'Hardware module reconciliation failed; check NetBox connectivity and API permissions')


if __name__=='__main__':main()
