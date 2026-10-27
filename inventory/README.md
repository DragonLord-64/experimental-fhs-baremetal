# Inventory

This directory is the **single source of truth** for what hosts exist,
what role each host plays, and what configuration each host needs.

## Layout

```
inventory/
  README.md
  netbox_placeholder.yml          # future NetBox-backed dynamic inventory
  dev_env/
    hosts.yml                     # groups + host membership
    group_vars/                   # shared defaults and policy
      all.yml
      teraboxes.yml
      control_servers.yml
      ubuntu24_cis_all.yml
      ubuntu24_cis_prototype.yml
      ubuntu24_cis_production.yml
    host_vars/                    # per-host overrides (connection + flags)
      sys1353.yml
      sys1392.yml
```

Point Ansible at the environment directory, not at the file:

```bash
ansible-playbook -i inventory/dev_env site.yml
```

Ansible's directory-inventory mode auto-loads `hosts.yml`,
`group_vars/<group>.yml` and `host_vars/<host>.yml`. Capability groups do not
need separate vars files when their hosts share the `teraboxes` defaults.

## Group taxonomy

Groups are split on two orthogonal axes. A host can be in one
hardware-class group and any number of capability groups.

| Axis | Group | Meaning |
|---|---|---|
| **Hardware class** | `teraboxes` | FHS terabox compute nodes |
|  | `control_servers` | In-cluster service hosts (aptly, devpi, gitea) |
| **Capability** | `fpga` | Bittware FPGA card present — `fpga_host` role applies |
|  | `user_environments` | Shared Python venvs — `venvs` role applies |
|  | `distribution_access` | Use the internal Git, APT, and pip proxy services |

Playbooks target hosts by group (`hosts: fpga`) rather than by per-host
list variables. Use `--limit` to subset further at run time.



## Adding a host

1. Add the hostname to the relevant groups in `hosts.yml`.
2. Create `host_vars/<host>.yml` with at least `ansible_host` and any
   per-host overrides.
3. If the host represents a new functional capability, add the appropriate
   group entry in `hosts.yml`. Create a dedicated `group_vars/<group>.yml` only
   when that capability needs values that do not apply to every terabox.

## Future: NetBox integration

`netbox_placeholder.yml` is a stub for the eventual NetBox-backed
dynamic inventory. When that lands it will replace `dev_env/hosts.yml`
while keeping the same group taxonomy.

## Ubuntu 24 policy membership

`ubuntu24_cis_production` contains `linux_servers`, whose children are the known
FPGA server role, `control_servers` and `fhs_nodes`. This policy is independent of
Kubernetes membership. Merge `hosts.yml` with NetBox by using `-i inventory/dev_env`.
For a different NetBox Linux role, set config context `fhs_linux_server: true`, or
add explicit membership to `linux_servers`. Do not guess platform names or include
switches. Check `playbooks/site.yml --list-hosts --tags ubuntu24_cis` before apply.
The selected policy enforces Ubuntu 24 settings; firewall work is excluded and the
network role owns timesyncd. See [site policy notes](../docs/src/playbooks/site.yml.md).
