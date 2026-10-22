# site.yml

Ansible repository for provisioning SKA Mid.CBF FHS baremetal nodes.

For information on Ansible see: [ansible-docs](https://docs.ansible.com/)

## Quick start

```bash
# One-time after clone: Python tooling (needs network)
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt   # or: poetry install --with test
source .venv/bin/activate

# Validate playbook structure and syntax configurations
ansible-playbook playbooks/syntax_check.yml --syntax-check

# Apply the full post-provisioning pipeline against target systems
ansible-playbook -i inventory/dev_env playbooks/site.yml

# Useful subsets
ansible-playbook -i inventory/dev_env playbooks/site.yml --tags users
ansible-playbook -i inventory/dev_env playbooks/site.yml --limit sys1353 --tags fpga,config
ansible-playbook -i inventory/dev_env playbooks/site.yml --skip-tags hardware,destructive
```

See `playbooks/README.md` for role-level documentation, testing guidelines, and tag conventions.

## Roles

Roles are defined under the top level `/roles` directory, which is referenced by the `roles_path` argument in the `ansible.cfg` file.

| Role | Applies to | Purpose |
|---|---|---|
| `apt_repo_access` | `distribution_access` | Configure apt to use an apt proxy |
| `bist` | `fhs_nodes` | Install and startup BIST (built-in self test) |
| `bittware_sdk` | `user_environments` | Installs the BittWare SDK |
| `fpga_host` | `fpga` | Bittware FPGA packages, GRUB, udev, SDK, BMC firmware |
| `fhs_node_setup` | `fhs_nodes` | Set up the FHS servers as Kubernetes nodes (without joining cluster) |
| `install_dpdk` | `dpdk_enabled` | Installs and configures DPDK, Arkville, and NVIDIA DOCA |
| `network_setup` | all | systemd-networkd interface + disable cloud-init |
| `pip_index` | `distribution_access` | Configure pip to use the internal devpi mirror |
| `ubuntu24_cis` | `fhs_nodes` | Hardens systems against the Ubuntu 24.04 CIS benchmark |
| `users` | all | Create accounts, sudo groups, SSH keys |
| `venvs` | `user_environments` | Create shared Python venvs |

## Getting Started

Before running any playbooks, ensure off-the-shelf vendor collections and roles are installed locally:

```bash
ansible-galaxy collection install -r requirements.yml -p <path to collections folder>
ansible-galaxy role install -r requirements.yml -p <path to roles folder>
```

## Usage

Run all playbooks from the root directory of this repository so that the local `ansible.cfg` path mappings are applied correctly:

```bash
ansible-playbook -i inventory/dev_env playbooks/site.yml
```

## Tag conventions

Three orthogonal axes — every task carries at most one of each:

- **Component**: `apt_repo`, `aptly_server`, `bist`, `bittware`, `devpi_server`, `dpdk`, `fpga`, `fhs_node_setup`, `gitea_server`, `network`, `pip_index`, `users`, `venvs`
- **Phase**: `install`, `config`, `firmware`
- **Risk**: `hardware` (can't run in containers), `destructive`, `insecure`, `never` (opt-in only)

```bash
# Safe-in-container subset:
ansible-playbook playbooks/site.yml --skip-tags hardware

# Update Bittware BMC firmware on one host (opt-in via `never`):
ansible-playbook playbooks/site.yml --tags fpga,firmware,bmc_firmware --limit sys1353
```