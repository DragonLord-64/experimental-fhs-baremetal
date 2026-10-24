# NetBox and switch playbooks

NetBox discovery/export lives under `playbooks/netbox/`; switch POAP and Nexus configuration live under `playbooks/switch-poap/`. Their tasks, plugins and supporting scripts moved together without behavior changes. Other development playbooks remain in place. Run from `/provision` with the required collections, Python packages and private variables available.

## NetBox discovery and export

| Playbook | Ownership |
|---|---|
| `netbox/netbox_import.yml` | One importer for Linux servers and Nexus switches; routes selected hosts before discovery. |
| `netbox/bifrost_export.yml` | Reads selected NetBox servers and protected Redfish credentials; writes private inventory without enrollment. |

Install the NetBox helper dependencies from `playbooks/netbox/requirements.yml` and `requirements.txt`. Imports require authorized hardware access and writable NetBox credentials. They are not documentation checks. See [inventory and export](../guide/using_netbox_inventory.md).

Use one command for mixed or limited inventories:

```bash
ansible-playbook -i <PRIVATE_INVENTORY> playbooks/netbox/netbox_import.yml \
  -e netbox_credentials_file=<PRIVATE_NETBOX_VARS> --limit <HOST_OR_GROUP> --tags compare
```

Nexus hosts are selected by group `nexus`, role group `device_roles_nexus-switch`
(or underscore spelling), or `ansible_network_os: cisco.nxos.nxos` (`nxos` alias
accepted). They use `network_cli`; other supported hosts use Linux discovery.
Routing happens locally before either family, and separate plays keep Linux
fleet ownership checks scoped to servers. `facts` / `compare` / `--check` retain
read-only behavior; `apply` writes the selected scope. The old
`netbox_import_nexus.yml` is only a Nexus-scoped compatibility wrapper.

## Asset reconciliation

Chassis identity is the observed DMI `product_serial` (`bootstrap_chassis_serial`
can explicitly override it), with discovered `system_vendor` and `product_name`
or the existing `bootstrap_manufacturer` / `bootstrap_device_type` overrides.
A hostname is a mutable device name. Conflicting names/serials, missing physical
serials and assigned/quarantined asset conflicts require review; no synthetic
identity is invented. DDR5/NVMe items need both a part and serial; unknown items
are omitted and prevent complete-scope removal.

OEM placeholders are unavailable identities. An IPMI FRU motherboard serial is
not a chassis serial; never use it as a fallback. Keep board/chassis sources
distinct and use a verified explicit chassis override when DMI is unavailable.
On real hardware, inspect `--tags facts` first and compare BIOS/BMC versions
against their distinct sources before `--tags compare` and a limited apply.

`fhs_fpga_sync` and `fhs_inventory_sync` reconcile Inventory assets by hardware
type + serial. Repeat imports reuse the asset. A different bay serial deletes
and recreates the installed record, leaves the original asset stored and writes
old/new serial, bay and result to the parent device journal. Chassis replacement
requires explicit review; it cannot be inferred from a reused hostname.

Absence removal defaults off. Opt in with `bootstrap_fpga_complete`,
`bootstrap_nic_complete`, `bootstrap_components_complete` plus
`bootstrap_component_scope: [DDR5, NVMe]`, or `bootstrap_nexus_complete` plus
`bootstrap_nexus_complete_bays` (exact bay names, defaults to observed bays).
A successful empty SDK report additionally requires an explicit
`bootstrap_fpga_empty_pattern`; unmatched card output cannot authorize removal.
The relevant discovery must also succeed completely; missing, failed, partial,
unselected or unidentified sections preserve inventory. FPGA/NIC removal stays
within their named bay prefixes. Component removal stays within explicitly
selected kinds created with `FHS managed <kind>` descriptions; operator-owned
items are preserved. A complete empty section differs from unavailable data.

Module removal detaches uncabled interfaces first, preserving their IDs. Cabled
interfaces or other module-owned components refuse removal pending review; the
journal records the cabled refusal. Prior cabling is never treated as newly
verified or copied to a replacement. Transceivers/DACs have only observed local
ends; a standalone DAC asset may be managed manually without a native Cable.
The importer refuses to install a `faulty` asset until explicitly reviewed.

REST operations span requests and are not one database transaction. On failure,
inspect the parent journal and retained assets before retrying. NetBox change-log
retention follows platform configuration (default 90 days); journals are retained
with the parent device and must be backed up for a durable record.

The common discovery YAML export/import boundary remains design work. Current
entrypoints discover live facts and call native modules directly; this change
does not introduce a general offline discovery framework. Synthetic CLI/API
coverage is described in the [alignment checks](../../../ops/platform/inventory-alignment/README.md).

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
