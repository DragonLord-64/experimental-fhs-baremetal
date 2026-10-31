# site.yml

Applies configuration to installed FHS servers. [provision.yml](provision.yml.md) wraps this playbook with inventory assertions and a summary.

## Roles and tags

Each role include has its exact role name as a tag. Most plays target `device_roles_fpga-host-server`, including `setup_k8s_node` and the enabled installation-only `manage_fhs_bist`; external `ubuntu24_cis` targets the independent `ubuntu24_cis_production` Linux policy group. Confirm that group exists in the resolved inventory; the current NetBox file creates `teraboxes` and device-role groups, not `fhs_nodes`.

| Play tag | Role tags |
|---|---|
| `foundation` | `setup_fhs_network` |
| `distribution` | `setup_platform_ca`, `python_ca_updates` (Ubuntu packages), `setup_apt_source`, `setup_pip_source`, `setup_git_proxy` |
| `environment` | `manage_users` (accounts, SDK, shared and personal venvs) |
| `dpdk_arkville` | `manage_dpdk_ark_doca` |
| No play tag | `setup_k8s_node`, `manage_fhs_bist` |
| `ubuntu24_cis` | `ubuntu24_cis` |
| `rsync` | Final package/service tasks (no role) |
| No play tag | `manage_fhs_exporter`, `manage_prometheus`, `filebeat`, `setup_fpga_host` |
| `always`, `audit_python_ca` | Final read-only Python/CA audit, including tagged provisioning runs |

FSP/VCC gRPC controllers are supported services managed by `manage_fhs_grpc`;
`site.yml` currently does not include their installation. The
[certificate-update playbook](certificate-update.md) is a one-off security
remediation. Its optional controller cleanup stops and removes affected
installations; controller redeployment is a separate step. `manage_fhs_bist` only
installs/configures its placeholder and does not start hardware tests.

Additional accounts, including the local development account and `gitlab-runner`, are configured in `fhs_users` in environment group vars. Use `--tags manage_users` to configure those accounts and their SDK environments. Review the selected scope before applying the whole playbook. Multiple tags use OR selection. Firmware requires both its flag and explicit `firmware` selection; `never` alone is not a safety boundary.

## Commands

Use [preflight](preflight.md) to check selected inputs before applying roles.

From the repository root, install the declared collections and external roles into the configured paths:

```bash
ansible-galaxy collection install -r requirements.yml -p <COLLECTIONS_PATH>
ansible-galaxy role install -r requirements.yml -p <ROLES_PATH>
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --list-hosts
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags manage_prometheus
```

The final command changes the host. Use the table above to select a role tag;
`--list-tasks` and `--list-tags` do not enumerate every nested task. Each role's
README shows its settings and commands.

## Ubuntu 24 CIS scope

In NetBox, create a tag with slug `ubuntu24-hardening` and assign it to each
Ubuntu 24.04 server that should receive this policy. Servers with any device
role can use this tag, including `fpga-host-server`.

`inventory/dev_env/netbox-inv.yml` selects the tagged devices:

```yaml
groups:
  ubuntu24_cis_production: "'ubuntu24-hardening' in (tags | default([]) | map(attribute='slug') | list)"
```

The `ubuntu24_cis` command tag selects the hardening tasks; the NetBox tag
selects their hosts. The inventory also requires devices to be active and have
a primary IP address.

Confirm the policy scope before applying it:

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --list-hosts --tags ubuntu24_cis
```

The role requires Ubuntu 24.04. Keep switches out of this policy group.

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

## Package sources and logging

Edit the split group vars under
`inventory/dev_env/group_vars/device_roles_fpga-host-server/` before applying.
`distribution.yml` selects the platform endpoints: signed APT over the HTTP
cache, verified HTTPS pip and an HTTP Git proxy tunnelling verified HTTPS.
`monitoring.yml` selects the local packages and Elasticsearch endpoint.

```bash
# Configure public CA trust and distribution clients.
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags distribution
# Load Elasticsearch index assets without installing a controller service.
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/filebeat_setup.yml --limit <HOST>
# Install the selected Filebeat package on the server after setup succeeds.
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags filebeat
```

[Controller trust and inventory](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/inventory/README.md) must be ready
before these commands. [Filebeat](../roles/filebeat.md) documents
the separate setup and publishing credentials.
