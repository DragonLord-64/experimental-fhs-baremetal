# NetBox and switch playbooks

NetBox discovery/export lives under `playbooks/netbox/`; switch POAP and Nexus configuration live under `playbooks/switch-poap/`. Their tasks, plugins and supporting scripts moved together without behavior changes. Other development playbooks remain in place. Run from `/provision` with the required collections, Python packages and private variables available.

(import-servers-using-bifrost-inventory)=
## Import servers using Bifrost inventory

Inside the provisioning container, from `/provision`:

```bash
export BIFROST_INVENTORY_SOURCE=/bifrost/playbooks/inventory/terabox1501b_inventory.yaml
ansible-playbook -i localhost, playbooks/netbox/bifrost_import.yml \
  -e '{"bifrost_import_nodes":["sys1391","sys1412"],"bootstrap_site":"MDA","bootstrap_role":"fpga-host-server"}' \
  --tags compare
```

Replace names/site and repeat with `--tags apply` after reviewing the preview.
The wrapper installs controller-side `ipmitool`, reuses Bifrost BMC credentials
for remote FRU discovery and uses SSH for OS/components. No target-side IPMI
package is required. It reads the shared platform endpoints/Vault secrets and
never invokes Bifrost enrollment, cleaning or OS deployment. See
[adapter settings](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/playbooks/netbox/README.md#import-servers-from-bifrost-inventory).

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

Chassis identity comes from `bootstrap_chassis_serial`, Linux DMI
`chassis_serial`, then the selected IPMI FRU `Chassis Serial`. Product and board
serials remain separate. Usable DMI manufacturer/model values take precedence
over FRU; `bootstrap_manufacturer` / `bootstrap_device_type` override discovery.
A hostname is a mutable device name. Conflicting names/serials and assigned or
quarantined assets require review; no synthetic identity is invented.

Local `ipmitool fru` is optional. Missing tools, denied access, failed reads and
absent fields leave new optional values unset and preserve known NetBox values.
A device without a chassis serial gets no chassis asset. Existing devices can
retain their type; creating a device without manufacturer/model is skipped until
verified type overrides are supplied. DDR5/NVMe items still need part and serial.

See the [importer README](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/playbooks/netbox/README.md) for FRU selection,
field mapping and provenance. Inspect `--tags facts` before compare/apply;
BIOS, BMC firmware and FRU product version have separate sources.

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
verified or copied to a replacement. Topology discovery joins observed LLDP peers
and exact DAC serial matches after all selected devices are imported. Unresolved local transceivers remain inventory
only; a standalone DAC asset may also be managed manually. See the
[importer topology options](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/playbooks/netbox/README.md).
The importer refuses to install a `faulty` asset until explicitly reviewed.

Optional `/etc/server-info.yaml` keys `rack_unit` and `power_ports` add native
placement and independent server inlet-to-PDU-outlet cables. Keep existing
site/role/location/rack fields. See the [metadata schema](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/playbooks/netbox/README.md#optional-server-placement-and-power).
Missing new metadata preserves existing records; identities and occupied
terminations must be resolved before apply.

```bash
ansible-playbook -i <PRIVATE_INVENTORY> playbooks/netbox/netbox_import.yml \
  --limit <HOST_OR_GROUP> --tags compare
ansible-playbook -i <PRIVATE_INVENTORY> playbooks/netbox/netbox_import.yml \
  --limit <HOST_OR_GROUP> --tags apply
```

Both read `/provision/files.d/platform-endpoints.yml` and the encrypted
`/provision/files.d/credentials/platform-secrets.yml`. Set
`FHS_PLATFORM_ENDPOINTS_FILE` / `FHS_PLATFORM_SECRETS_FILE` to select other
controller locations. SDK discovery uses the configured
BittWare venv/root/account and never installs packages. Dynamic QSFP ports retain
empty interfaces; only verified FPGA DAC identities supplement LLDP.


REST operations span requests and are not one database transaction. On failure,
inspect the parent journal and retained assets before retrying. NetBox change-log
retention follows platform configuration (default 90 days); journals are retained
with the parent device and must be backed up for a durable record.

The common discovery YAML export/import boundary remains design work. Current
entrypoints discover live facts and call native modules directly; this change
does not introduce a general offline discovery framework. Validate hardware
identities and selected discovery scopes before comparing and applying them.

## Switch POAP

1. Populate switch records, serials and enabled `mgmt0` interfaces with MAC and IP addresses in NetBox.
2. Inside the configured Bifrost environment, run `switch-poap/configure_bifrost_dhcp.yml` for the entire switch group (default `device_roles_nexus-switch`). It replaces shared DHCP host/option files, writes the serial-to-IP mapping, copies `poap_script.py` into TFTP storage and signals dnsmasq to reload. Supply `poap_url` explicitly; the current implementation advertises it as DHCP option 66 and `poap_script.py` as option 67.
3. After POAP, use `switch-poap/configure_nexus.yml` for identity and telemetry. It tries inventory SSH keys, then a source-defined bootstrap fallback. Protect and replace bootstrap access. `--tags provision` configures hostname, users and `nxos_telemetry_commands`; private `*.hash` and `*.pub` files come from `nexus_credentials_dir`.
4. Port settings (`--tags ports`) and physical breakout (`--tags breakout`) are separate opt-ins. `nexus_ports.yml` supplies declarations; default native 400G is not proof of physical support. Breakout resets selected interfaces and requires hardware review.

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/switch-poap/configure_bifrost_dhcp.yml --list-hosts
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/switch-poap/configure_nexus.yml --list-tags
```

Listing is read-only but inventory polling needs private access. Even without opt-in tags, Nexus authentication tasks run; do not use an untagged execution as a safety check.

Source directories: `playbooks/netbox/` and `playbooks/switch-poap/`.
