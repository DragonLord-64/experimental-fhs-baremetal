# provision.yml

Validates `ansible_host` and `sys_mac_address`, imports `site.yml`, then reports the selected hosts. This configures an installed OS; it does not enroll or image Bifrost nodes.

## Workflow

Run from `/provision` in the configured provisioning container, or the repository root with its dependencies installed. Select the inventory and host limit explicitly.

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/provision.yml --list-hosts
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/provision.yml --limit <HOST> --tags manage_users
```

The second command changes the selected host. See [site.yml](site.yml.md) for role selection and [NetBox inventory](../guide/using_netbox_inventory.md) for credentials and grouping. Tag selection also filters the input assertions; it does not replace inventory validation.
