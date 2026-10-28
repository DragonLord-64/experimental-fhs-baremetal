# site.yml

Applies configuration to installed FHS servers. [provision.yml](provision.yml.md) wraps this playbook with inventory assertions and a summary.

## Roles and tags

Each role include has its exact role name as a tag. Most plays target `all`, including `setup_fhs_node` and the enabled installation-only `manage_fhs_bist`; external `ubuntu24_cis` targets the independent `ubuntu24_cis_production` Linux policy group. Confirm that group exists in the resolved inventory; the current NetBox file creates `teraboxes` and device-role groups, not `fhs_nodes`.

| Play tag | Role tags |
|---|---|
| `foundation` | `manage_users`, `setup_fhs_network` |
| `distribution` | `python_ca_updates` (Ubuntu packages), `setup_apt_source`, `setup_pip_source`, `setup_git_proxy` |
| `environment` | `manage_venvs`, `manage_bittware_sdk`, `manage_gitlab-runner` |
| `dpdk_arkville` | `manage_dpdk_ark_doca` |
| `fhs_node` | `setup_fhs_node`, `manage_fhs_bist` |
| `ubuntu24_cis` | `ubuntu24_cis` |
| `rsync` | Final package/service tasks (no role) |
| No play tag | `manage_fhs_exporter`, `manage_prometheus`, `filebeat`, `setup_fpga_host` |
| `always`, `audit_python_ca` | Final read-only Python/CA audit, including tagged provisioning runs |

FSP/VCC gRPC installation is retired. Use
[the tagged certificate cleanup](certificate-update.md) in
`playbooks/development/certificate-update.yml` to remove existing services and
environments before recreating the provisioning venvs. `manage_fhs_bist` only
installs/configures its placeholder and does not start hardware tests.

The `local_dev` play sets a local account password from protected variables; it is included by an unrestricted run. Review the selected scope before applying the whole playbook. Multiple tags use OR selection. Firmware requires both its flag and explicit `firmware` selection; `never` alone is not a safety boundary.

## Commands

From the repository root, install the declared collections and external roles into the configured paths:

```bash
ansible-galaxy collection install -r requirements.yml -p <COLLECTIONS_PATH>
ansible-galaxy role install -r requirements.yml -p <ROLES_PATH>
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --list-hosts
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags manage_prometheus
```

The final command changes the host. See the role pages for defaults and explicit functional/safety tags. Dynamic includes mean `--list-tasks` and `--list-tags` do not enumerate all internal tasks. Development `config.yml` and `syntax_check.yml` retain stale imports; they are not verified validation entry points.

## Ubuntu 24 CIS scope

Use `-i inventory/dev_env` to merge explicit Linux group membership with NetBox.
The policy group includes `linux_servers` (known FPGA server role, control servers
and FHS nodes). The NetBox file also selects the known `fpga-host-server` role/tag;
other Linux roles must set `fhs_linux_server: true` in NetBox config context or be
explicitly placed in `linux_servers` in `hosts.yml`. No platform names are guessed.
Switches must not be placed in this group. Confirm `--list-hosts --tags ubuntu24_cis`
contains every intended Linux host before applying; the role requires Ubuntu 24.04.

`inventory/dev_env/group_vars/ubuntu24_cis_production.yml` supplies the effective
policy to every selected host, including non-Kubernetes servers. Enforcement
(`audit_only: false`) is intentional and no longer hidden in an include override.
Preflight checks the effective OS/policy before external-role writes: no reboot,
no firewall section, no Chrony/time-service changes and no audit storage actions
that halt the host. The network role owns systemd-timesyncd. Approved development
NOPASSWD sudo remains excluded from CIS password enforcement.

Patching, password-quality and AIDE controls remain deferred for user policy
review; their disabled state is not evidence of deployed insecurity. This is
selected-policy wiring verification, not a CIS application/compliance result.
Install external `ubuntu24_cis` at the declared 1.6.0 version; supply the existing
Goss binary/audit archive before an authorized apply.

Configure inventory membership, reviewed versions, DNS/NTP and protected discovery
credentials before running the playbook.

The final `rsync` play preserves the upstream package/service tasks outside the
FPGA role; it does not configure modules or authentication. Supply an approved
rsync daemon configuration before enabling it on real hosts.


## Prerequisites

Supply inventory settings for shared BittWare identity, approved development users,
Linux CIS policy membership, Kubernetes/runtime versions, network MAC/address/prefix,
DNS/NTP and reachable proxy URLs. Install the platform services before configuring
clients to use them.

Provide the bitstream, SDK, DOCA and build archives,
monitoring packages and protected setup/publishing
credentials. `site.yml` and `provision.yml` are the entry points.
