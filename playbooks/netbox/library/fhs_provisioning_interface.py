#!/usr/bin/python
"""Adopt the bootstrap provisioning interface by its observed MAC."""
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.fhs_netbox import Sync


def reconcile(sync, device_id, interfaces):
    ports = sync.list('dcim/interfaces/', device_id=device_id)
    temporary = [p for p in ports if p['name'] == 'provisioning'
                 and any(t.get('slug') == 'provisioning-interface' for t in p.get('tags', []))]
    renames = {}
    pending = []
    for port in temporary:
        macs = sync.list('dcim/mac-addresses/', assigned_object_id=port['id'],
                         assigned_object_type='dcim.interface')
        addresses = {m['mac_address'].lower() for m in macs}
        observed = [i for i in interfaces if i.get('mac', '').lower() in addresses]
        if len(observed) > 1:
            raise ValueError('Multiple observed interfaces match the temporary provisioning MAC')
        if not observed or observed[0]['name'] == port['name']:
            continue
        name = observed[0]['name']
        if any(p['name'] == name for p in ports):
            raise ValueError('Observed provisioning interface name already exists; review the duplicate')
        renames[name] = port['name']
        pending.append((port, name))
    for port, name in pending:
        sync.ensure('dcim/interfaces/', {'id': port['id']}, {'name': name},
                    'Rename provisioning interface to ' + name)
    return renames


def main():
    module = AnsibleModule(argument_spec=dict(
        netbox_url=dict(required=True), netbox_token=dict(required=True, no_log=True),
        validate_certs=dict(type='bool', default=True), device_id=dict(type='int', required=True),
        interfaces=dict(type='list', elements='dict', required=True),
        preview=dict(type='bool', default=False)), supports_check_mode=True)
    try:
        sync = Sync(module.params, module.check_mode or module.params['preview'])
        renames = reconcile(sync, module.params['device_id'], module.params['interfaces'])
        module.exit_json(changed=bool(sync.plan), renames=renames, plan=sync.plan)
    except Exception as error:
        module.fail_json(msg=str(error))


if __name__ == '__main__':
    main()
