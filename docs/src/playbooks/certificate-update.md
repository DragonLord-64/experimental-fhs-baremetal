# Certificate cleanup

`playbooks/development/certificate-update.yml` updates CA trust and removes old
Python environments before normal provisioning recreates them. FSP/VCC gRPC
installation is retired from `site.yml`; cleanup is a block in this playbook.

Targets `device_roles_fpga-host-server`; use the current NetBox inventory.

```sh
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/development/certificate-update.yml --limit <HOST> --ask-vault-pass
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/development/certificate-update.yml --limit <HOST> --ask-vault-pass --tags remove_fhs_grpc
```

An untagged run selects all blocks, in this order:

| Tag | Action |
|---|---|
| `update_ca` | Update Ubuntu's `ca-certificates` package. |
| `verify_ca` | Decode the system bundle and require the removed emSign root to be absent. |
| `remove_fhs_grpc` | Stop/disable both controllers and remove their units, installations and venvs. |
| `reset_venvs` | Delete `/opt/venvs/fhs` and `/home/gitlab-runner/.bw_venv`. |
| `refresh_snaps` | Refresh Snap packages if Snap is installed. |
| `audit_python_ca` | Final host validation after cleanup; also runs for tagged selections. |

Use comma-separated tags to select multiple blocks, or `--skip-tags refresh_snaps`
to omit Snap updates. Path guards stay inside each selected block. The final
host audit is tagged `always` and `audit_python_ca`; use `--tags audit_python_ca`
to validate alone, or an explicit `--skip-tags audit_python_ca` to defer it.

gRPC cleanup removes `/opt/grpc/{fsp,vcc,poetry}`, legacy `/etc/grpc/{fsp,vcc}`
and only `ska-mid-cbf-fhs-{fsp,vcc}-grpc-controller-*-py*` directories immediately
under `/root/.cache/pypoetry/virtualenvs`. Missing services/directories are accepted;
a service stop failure prevents deletion. Systemd reloads only when units changed.
Existing `remove_fhs_grpc_root`, `remove_fhs_grpc_legacy_root`,
`remove_fhs_grpc_unit_dir` and `remove_fhs_grpc_cache_dir` inventory overrides remain
supported. Review those roots for a non-default installation layout.

Shared bitstreams, SDK, hardware accounts/groups, personal gRPC projects,
unrelated Poetry environments and systemd drop-ins remain. The personal gRPC
certifi and shared virtualenv seed-cache audit findings need separate remediation
and will keep the final audit failing until addressed. Findings print their path,
meaning and next step before the playbook fails. INCOMPLETE checks also fail;
PASS means no known incident findings in the audit's documented scan scope.

After cleanup, recreate the provisioning venvs and rerun the audit:

```sh
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --ask-vault-pass --tags python_ca_updates,manage_users,audit_python_ca
```
