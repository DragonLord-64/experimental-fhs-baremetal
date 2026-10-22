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

## Operational NetBox and switch playbooks

- `netbox/`: server/switch discovery, NetBox updates and protected Bifrost inventory export.
- `switch-poap/`: POAP script, Bifrost DHCP integration and Nexus configuration.

These directories were promoted intact from development; task and plugin behavior is unchanged. Run only against explicitly authorized targets with private credentials. See [commands and prerequisites](../docs/src/playbooks/development.md). Other development playbooks remain in place.

[Archived playbooks](archive/README.md) retain the former CIS audit/prototype, node, BIST, gRPC, exporter/Prometheus, EXDS and Filebeat entry points with their current directions. The card test remains under development.
