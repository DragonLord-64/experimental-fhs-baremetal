# manage_fhs_network

systemd-networkd config for FHS hosts. Disables cloud-init networking and
removes legacy netplan files.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `sys_mac_address` | _required (host_vars)_ | Primary NIC MAC, matched by udev |
| `ansible_host` | _required (host_vars)_ | Static IPv4 of primary NIC |
| `network_interface_prefix` | `16` | CIDR prefix length |
| `network_dns` | `[172.17.0.95, 192.168.128.13]` | DNS servers |
| `network_ntp` | `[192.168.1.6, 192.168.1.7]` | NTP servers |
| `network_managed_files` | `[00-fhs.network, 99-ignore-others.network]` | Files in `network_dir` this role owns; anything else is removed |

Tags: `network`, `config`, `hardware`.
