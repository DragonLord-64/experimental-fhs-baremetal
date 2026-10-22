# provision.yml

This playbooks is the primary provisioning playbook. It will be applied to all FHS servers and contains all the required roles for an FHS. This playbooks directly call site.yml which handles to individual role imports.

For information on Ansible see: [ansible-docs](https://docs.ansible.com/)

## Quick start

```bash
# connect to provisioning container

# Apply the full post-provisioning pipeline against target systems
ansible-playbook  playbooks/provision.yml # inventory is inferred based on ansible.cfg

# Useful subsets
ansible-playbook -i inventory/dev_env playbooks/provision.yml --tags users
ansible-playbook -i inventory/dev_env playbooks/provision.yml --limit sys1353 --tags fpga,config
ansible-playbook -i inventory/dev_env playbooks/provision.yml --skip-tags hardware
```

## Tasks
This playbook primary task is to call [site.yml](site.yml.md) which contains the role import tasks. 