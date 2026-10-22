# midcbf.fhs

Ansible repository for provisioning SKA Mid.CBF FHS baremetal nodes.

## Quick start

```bash
# One-time after clone: Python tooling (needs network)
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # or: poetry install --with test
source .venv/bin/activate


ansible-galaxy role install -r requirements.yml -p <path to roles folder>

# Validate playbook structure and syntax configurations
ansible-playbook playbooks/syntax_check.yml --syntax-check

# Apply the full post-provisioning pipeline against target systems
ansible-playbook -i inventory/dev_env playbooks/provision.yml

# Useful subsets
ansible-playbook -i inventory/dev_env playbooks/provision.yml --tags users
ansible-playbook -i inventory/dev_env playbooks/provision.yml --limit sys1353 --tags fpga,config
ansible-playbook -i inventory/dev_env playbooks/provision.yml --skip-tags hardware,destructive
```



See [Usage](../docs/src/playbooks/usage.md) for details