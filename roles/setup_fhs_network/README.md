# setup_fhs_network

Configures the primary IPv4 NIC directly with systemd-networkd. No Netplan
migration. Required MAC, address and prefix are checked before writes.

| Variable | Default | Purpose |
|---|---|---|
| `sys_mac_address` | required | Primary NIC MAC |
| `ansible_host` | required | Static IPv4 address |
| `network_interface_prefix` | `16` | IPv4 prefix, 0–32 |
| `network_dns` | `[172.17.0.95, 192.168.128.13]` | DNS servers for resolved |
| `network_ntp` | `[192.168.1.6, 192.168.1.7]` | Authorized timesyncd servers |
| `network_domains` | `[]` | Optional DNS search/routing domains |
| `network_dir` | `/etc/systemd/network` | Network configuration directory |
| `network_disable_cloud_init` | `true` | Disable only cloud-init networking |
| `network_remove_legacy_netplan` | `false` | Explicitly retire the old cloud-init Netplan file |

Writes MAC-specific `00-fhs.network`; preserves unrelated network files and
retires only the old role-owned `99-ignore-others.network`. networkd uses the
first matching filename: inspect earlier matching files in `/etc`, `/run` and
`/usr/lib/systemd/network` before applying. Later files cannot override this NIC.

Installs/enables/starts systemd-networkd, systemd-resolved and systemd-timesyncd;
links `/etc/resolv.conf` to resolved's stub and configures NTP in
`/etc/systemd/timesyncd.conf.d/00-fhs.conf`. Changes restart only the affected
network/DNS/time services. The role owns these settings; CIS time rules are disabled.
Review existing Chrony/NTP installations before applying: APT may replace
conflicting time-daemon packages when installing timesyncd. Actual internal NTP synchronization needs user validation.

Cloud-init receives `cloud.cfg.d/99-fhs-disable-network-config.cfg`; other
cloud-init functions remain enabled. An existing `/etc/cloud/cloud-init.disabled`
is preserved: if a previous role created it, review and remove it separately to
restore other cloud-init functions. Legacy Netplan retirement requires explicit
`network_remove_legacy_netplan: true` after checking ownership and console access;
`network_legacy_netplan_file` defaults to `/etc/netplan/50-cloud-init.yaml`.

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags setup_fhs_network
```

Run with reviewed inventory and console access; applying network changes can
interrupt SSH. Offline fixtures cover files and configuration only. No isolated
VM was available for live network application, DNS reachability or time sync.
