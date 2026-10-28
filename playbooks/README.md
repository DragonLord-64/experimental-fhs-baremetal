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
ansible-playbook -i inventory/dev_env playbooks/provision.yml --tags manage_users
ansible-playbook -i inventory/dev_env playbooks/provision.yml --limit sys1353 --tags fpga,config
ansible-playbook -i inventory/dev_env playbooks/provision.yml --skip-tags hardware,destructive
```



See [Usage](../docs/src/playbooks/usage.md) for details

The full site run ends with the read-only [Python CA audit](../roles/audit_python_ca/README.md).
Run `playbooks/audit_python_ca.yml` separately or select `--tags audit_python_ca`.
FSP/VCC gRPC installation is retired. Use the
[tagged certificate cleanup](../docs/src/playbooks/certificate-update.md) to remove old services
and their environments before recreating the provisioning venvs.

## Operational NetBox and switch playbooks

- `netbox/`: server/switch discovery, NetBox updates and protected Bifrost inventory export.
- `switch-poap/`: POAP script, Bifrost DHCP integration and Nexus configuration.

These directories were promoted intact from development; task and plugin behavior is unchanged. Run only against explicitly authorized targets with private credentials. See [commands and prerequisites](../docs/src/playbooks/development.md). Other development playbooks remain in place.

[Archived playbooks](archive/README.md) retain the former CIS audit/prototype, node, BIST, gRPC, exporter/Prometheus, EXDS and Filebeat entry points with their current directions. The card test remains under development.
