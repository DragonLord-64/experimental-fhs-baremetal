# NetBox and switch playbooks

NetBox discovery/export lives under `playbooks/netbox/`; switch POAP and Nexus configuration live under `playbooks/switch-poap/`. Their tasks, plugins and supporting scripts moved together without behavior changes. Other development playbooks remain in place. Run from `/provision` with the required collections, Python packages and private variables available.

## NetBox discovery and export

| Playbook | Ownership |
|---|---|
| `netbox/netbox_import.yml` | Discovers servers and writes NetBox records; BittWare discovery is enabled by default. |
| `netbox/netbox_import_nexus.yml` | Reads Nexus inventory, software and transceivers over `network_cli`, then populates NetBox. Targets `nexus`. |
| `netbox/bifrost_export.yml` | Reads selected NetBox servers and protected Redfish credentials; writes private inventory without enrollment. |

Install the NetBox helper dependencies from `playbooks/netbox/requirements.yml` and `requirements.txt`. Imports require authorized hardware access and writable NetBox credentials. They are not documentation checks. See [inventory and export](../guide/using_netbox_inventory.md).

## Switch POAP

1. Populate switch records, serials and enabled `mgmt0` interfaces with MAC and IP addresses in NetBox.
2. Inside the configured Bifrost environment, run `switch-poap/configure_bifrost_dhcp.yml` for the entire switch group (default `device_roles_nexus-switch`). It replaces shared DHCP host/option files, writes the serial-to-IP mapping, copies `poap_script.py` into TFTP storage and signals dnsmasq to reload. Supply `poap_url` explicitly; the current implementation advertises it as DHCP option 66 and `poap_script.py` as option 67.
3. After POAP, use `switch-poap/configure_nexus.yml` for identity and telemetry. It tries inventory SSH keys, then a source-defined bootstrap fallback. Protect and replace bootstrap access. `--tags provision` configures hostname, users and `nxos_telemetry_commands`; private `*.hash` and `*.pub` files come from `nexus_credentials_dir`.
4. Port settings (`--tags ports`) and physical breakout (`--tags breakout`) are separate opt-ins. `nexus_ports.yml` supplies declarations; default native 400G is not proof of physical support. Breakout resets selected interfaces and requires hardware review.

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/switch-poap/configure_bifrost_dhcp.yml --list-hosts
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/switch-poap/configure_nexus.yml --list-tags
```

Listing is read-only but inventory polling needs private access. Even without opt-in tags, Nexus authentication tasks run; do not use an untagged execution as a safety check. No physical POAP or Cisco telemetry validation is claimed for the private lab.

[NetBox helpers](https://github.com/DragonLord-64/experimental-fhs-baremetal/tree/development/playbooks/netbox) and [switch POAP implementation](https://github.com/DragonLord-64/experimental-fhs-baremetal/tree/development/playbooks/switch-poap).
