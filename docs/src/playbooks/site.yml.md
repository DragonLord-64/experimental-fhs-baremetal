# site.yml

Applies configuration to installed FHS servers. [provision.yml](provision.yml.md) wraps this playbook with inventory assertions and a summary.

## Roles and tags

Each role include has its exact role name as a tag. Most plays target `all`; `setup_fhs_node`, `manage_fhs_bist` and external `ubuntu24_cis` target `fhs_nodes`. Confirm that group exists in the resolved inventory; the current NetBox file creates `teraboxes` and device-role groups, not `fhs_nodes`.

| Play tag | Role tags |
|---|---|
| `foundation` | `manage_users`, `setup_fhs_network` |
| `distribution` | `setup_apt_source`, `setup_pip_source`, `setup_git_proxy` |
| `environment` | `manage_venvs`, `manage_bittware_sdk`, `manage_gitlab-runner` |
| `dpdk_arkville` | `manage_dpdk_ark_doca` |
| `fhs_node` | `setup_fhs_node`, `manage_fhs_bist`, `ubuntu24_cis` |
| No play tag | `manage_poetry`, `manage_fhs_grpc`, `manage_fhs_exporter`, `manage_prometheus`, `filebeat`, `setup_fpga_host` |

The `local_dev` play sets a local account password from protected variables; it is included by an unrestricted run. Review the selected scope before applying the whole playbook. Multiple tags use OR selection. `--skip-tags hardware` does not establish container safety.

## Commands

From the repository root, install the declared collections and external roles into the configured paths:

```bash
ansible-galaxy collection install -r requirements.yml -p <COLLECTIONS_PATH>
ansible-galaxy role install -r requirements.yml -p <ROLES_PATH>
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --list-hosts
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags manage_prometheus
```

The final command changes the host. See the role pages for defaults and internal tags. Dynamic includes mean `--list-tasks` and `--list-tags` do not enumerate all internal tasks. Development `config.yml` and `syntax_check.yml` retain stale imports; they are not verified validation entry points.
