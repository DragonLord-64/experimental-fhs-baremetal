#!/usr/bin/python
"""Reconcile observed Nexus management addresses through the native API client."""
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.fhs_netbox import Sync, physical_device
from ansible.module_utils.fhs_nexus_management import observe, reconcile


def main():
    module = AnsibleModule(argument_spec=dict(netbox_url=dict(required=True), netbox_token=dict(required=True, no_log=True),
        validate_certs=dict(type='bool', default=True), device=dict(required=True), serial=dict(required=True),
        output=dict(default=''), include_ips=dict(type='bool', default=True), preview=dict(type='bool', default=False)),
        supports_check_mode=True)
    try:
        sync = Sync(module.params, module.check_mode or module.params['preview'])
        observation = observe(module.params['output'])
        parent = physical_device(sync, module.params['device'], module.params['serial'])
        diagnostics = reconcile(sync, parent, observation, module.params['include_ips'])
        module.exit_json(changed=bool(sync.plan), plan=sync.plan, observation=observation, diagnostics=diagnostics)
    except Exception as error:
        module.fail_json(msg=str(error) if isinstance(error, ValueError) else 'Management reconciliation failed; inspect protected diagnostics')


if __name__ == '__main__':
    main()
