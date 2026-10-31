# NetBox import and export

Run from `/provision` with `requirements.yml`, `requirements.txt`, protected
NetBox variables and a selected inventory scope. See the
[development playbooks](../../docs/src/playbooks/development.md) for commands,
asset reconciliation and Nexus routing.

The default endpoint/credential file locations are set in [defaults.yml](defaults.yml).
Import plays and Bifrost export read the shared `platform-endpoints.yml` and
Vault-encrypted `platform-secrets.yml`. Override controller paths with
`FHS_PLATFORM_ENDPOINTS_FILE` / `FHS_PLATFORM_SECRETS_FILE`. The defaults file
holds SDK/NIC discovery, topology commands, API retries, certificate validation,
site/role defaults and Bifrost export settings. Override individual settings
per run with `-e key=value`.

## Import servers from Bifrost inventory

Run inside the provisioning container from `/provision`. Use the existing
Bifrost YAML/JSON node mapping; no separate bootstrap inventory is required.

```bash
export BIFROST_INVENTORY_SOURCE=/bifrost/playbooks/inventory/terabox1501b_inventory.yaml

ansible-playbook -i localhost, playbooks/netbox/bifrost_import.yml \
  -e '{"bifrost_import_nodes":["sys1391","sys1412"],"bootstrap_site":"MDA","bootstrap_role":"fpga-host-server"}' \
  --tags compare
```

Replace the node names and physical NetBox site name. `bootstrap_site` is not a
URL. The node's OS hostname becomes its NetBox name; the verified FRU serial
identifies its physical chassis. No serial is inferred from a Bifrost node name.

After reviewing the preview, repeat with `--tags apply`. The same stage tags
listed below work with this wrapper. Omitting `bifrost_import_nodes` selects all
nodes in the Bifrost file. If using `--limit`, include `localhost` so the adapter
can run.

The adapter reads `name`, `ipv4_address` (or `ansible_host`) and `driver_info`.
It uses `ipmi_address`, `ipmi_username`, `ipmi_password` and optional `ipmi_port`.
For existing Redfish entries it uses the host from `redfish_address` and the
Redfish username/password for network IPMI; HTTPS port 443 does not become the
IPMI port. These BMC accounts must also have network IPMI enabled. IPMI defaults
to UDP 623 using `lanplus`.

Shared `driver_info` defaults are read from `group_vars/baremetal` beside the
Bifrost source file; node settings override those defaults. Set
`bifrost_inventory_defaults_file` to another defaults file if needed.
Vault-encrypted source/default files are supported. Missing credentials or
ambiguous OS/BMC mappings stop before importing.

SSH defaults to `ubuntu`; change it with `-e bifrost_import_ssh_user=<USER>`.
Per-node `ansible_user`, `ansible_ssh_private_key_file` and
`ansible_python_interpreter` are accepted. The usual `-e ansible_user=...` and
SSH options also apply. The target still needs SSH and Python for OS/component
inventory; it does not need `ipmitool` for FRU or BMC reads in this workflow.

The wrapper installs `ipmitool` on the controller/provisioning container before
reading hardware, including preview/check-mode runs. A non-root controller needs
sudo for that package installation. It does not install packages on the target
servers, enroll/provide Ironic nodes, clean disks or deploy an OS.

FRU, BMC firmware and BMC LAN reads execute on the controller. Passwords pass
through the client environment, not command arguments; credential tasks suppress
logs. A failed remote FRU probe or missing system serial stops that host before
NetBox writes. Existing explicit identity overrides still apply. Module reads
are bounded by `netbox_ipmi_timeout` (45 seconds by default).

The shared platform endpoints and Vault secrets are loaded by the normal
importer. Switches still use their own inventory/connection settings; use
`netbox_import.yml` for a combined server/switch topology run.

## Import stages

```bash
ansible-playbook -i INVENTORY playbooks/netbox/netbox_import.yml --tags servers
ansible-playbook -i INVENTORY playbooks/netbox/netbox_import.yml --tags modules
ansible-playbook -i INVENTORY playbooks/netbox/netbox_import.yml --tags interfaces
ansible-playbook -i INVENTORY playbooks/netbox/netbox_import.yml --tags ips
ansible-playbook -i INVENTORY playbooks/netbox/netbox_import.yml --tags cables
```

No tags (or `--tags apply`) runs all stages. Combine stages with commas.
`--check` / `--tags compare` previews existing-parent changes without writes.

| Stage | Writes |
|---|---|
| `servers` | Chassis immediately after FRU identity, then OS, firmware, resources and available rack/location |
| `modules` | Observed motherboard/FRU PSUs, DIMMs, physical NVMe drives, FPGA/NIC cards, QSFPs and switch modules |
| `interfaces` | Host/switch interfaces, MACs and observed card associations |
| `ips` | Host addresses, primary IPv4 and available BMC out-of-band address |
| `cables` | LLDP/DAC connections, QSFP metadata/assets and explicit server-info power mappings |

Linux host interfaces must have `/sys/class/net/<name>/device` hardware backing;
this includes physical USB NICs and excludes loopback, container interfaces,
bridges and tunnels. IP and LLDP imports use the same physical interface set.
Explicit BMC and SDK-discovered FPGA ports are added separately. Existing logical
interface records are left untouched.

Shared component/type and pluggable writes run one host at a time to avoid
parallel hosts creating the same prerequisite records.

Later stages find the existing parent and skip it with a message if absent;
they do not create server records. NetBox may instantiate components already
defined in a module-type template. Physical cards and inventory items update in
place. Previous assets remain stored history when a different serial is observed.
Unobserved hardware is never removed, including with legacy `*_complete` flags.

Servers are tagged `fpga-host-server`, switches `nexus-switch`. Actual FRU part
numbers identify server models. New roles use `Unassigned` unless supplied through
`server-info` or `bootstrap_role`; missing role data preserves an existing role.
Partial server-info files are accepted. Explicit serial/manufacturer/part-number
metadata and bootstrap overrides take precedence over FRU values.

Occupied cable endpoints and conflicting IP/MAC ownership are reported and
preserved. Observed connections are created on unoccupied endpoints.

## Linux system identity

`netbox_import.yml` reads device identity from local `ipmitool fru` over SSH,
or controller-side network IPMI when the Bifrost adapter supplies BMC settings. Linux DMI facts and sysfs are not identity sources.
Local discovery uses the target’s existing privilege settings and installed tools.
The Bifrost wrapper installs the client on the controller and reads BMC credentials
from the Bifrost inventory.
`facts`, `compare` and check mode keep these probes read-only.

`system_fru_id` selects the system record (default `0`; older
`motherboard_fru_id` remains an alias). All FRU records are kept separately in
`fru_inventory`; other FRUs do not fill the selected record's missing fields.
Failed reads and missing/duplicate record IDs do not supply FRU identity fallbacks.

| NetBox destination | Discovery |
|---|---|
| Device serial / asset identifier | Explicit serial override, otherwise selected FRU **Product Serial** (`SYS1391`, etc.); no chassis/board/Linux fallback |
| Device type manufacturer | `bootstrap_manufacturer`, selected FRU Product Manufacturer; `NA` for a new serial-only device |
| Device type model | Explicit model override, otherwise FRU Product Part Number; `Unknown` for a new serial-only device |
| `product_*` device fields | Selected FRU Product fields; serial/version remain product identity |
| `motherboard_*` device fields | Selected FRU Board Mfg/Product/Serial, part number and manufacture date |
| Motherboard inventory item / asset | Only with observed board manufacturer, model and serial; board model identifies its type; part number is set only when observed |
| `chassis_serial`, `chassis_part_number`, `chassis_type` | FRU enclosure properties; never the server identifier |
| `manufacture_date` | FRU Product Name, retained as reported (`14-MAY-2025`); separate from motherboard manufacture date |
| `hardware_identity_sources` | Per-field source, including FRU ID and label |
| `fru_inventory` | Records keyed by FRU ID, with description and fields including additional product/board metadata |

Empty values and OEM placeholders are omitted. Date-shaped strings are retained
as observations but cannot identify a model. The selected FRU Product Serial identifies the server. Chassis Serial is
enclosure metadata and Board Serial identifies the motherboard component. Product
Name holds the server manufacturing date, not the device model. FRU Product Version is separate from BIOS
(`dmidecode --type bios`) and BMC firmware (`ipmitool mc info`).

Missing FRU data is normal. New optional fields stay empty; existing fields,
provenance, FRU records and assets survive partial reads. A missing product
serial permits hostname-based device updates without creating/reassigning an
asset; it cannot establish a rename. A valid FRU serial is sufficient to create
a device: missing manufacturer/model use `NA` / `Unknown` because NetBox requires
a type. Existing manufacturer/model are retained when FRU omits them. Valid FRU
manufacturer/model correct the existing device and linked chassis asset type; the asset ID, tag and history are preserved. Changes
are journalled with discovery sources. Explicit `bootstrap_chassis_serial`,
`bootstrap_manufacturer` and `bootstrap_device_type` override FRU values in the
same normalization step. Device updates use the ensured type ID.
Unambiguous hardware observations update installed serial/type values while
preserving record IDs, interfaces and cabling. Previous physical assets remain
in history; ambiguous duplicate device identities still require resolution.

A failed host stops its own import; other hosts and discovery families continue.
Only completed host imports contribute to shared topology. Ansible still returns
failure for the run when a host fails; inspect its recap before rerunning.

Discovery never enables absence removal. Legacy completeness flags do not
remove any installation. DIMM/NVMe component discovery keeps its existing Linux/tool sources.
Keep discovery output private because it contains hardware identifiers.

## Topology

`netbox_import.yml` routes selected Linux and NX-OS hosts, imports their inventory,
then reconciles topology once all selected inventories exist. Nexus model and
serial come from the chassis report. Unsupported network operating systems fail
before discovery.

Topology discovery is read-only: existing `lldpcli -f json show neighbors`,
`ethtool -m <physical NIC>`, `bw_qsfp_info -c <card index> -i USB display`, and
`show lldp neighbors detail | json`. It does not install or enable LLDP, change
ports, or write FPGA registers. Override `bootstrap_lldp_argv`,
`bootstrap_bittware_qsfp_argv`, or `nexus_lldp_command` for local tool paths.
`bootstrap_topology_enabled: false` skips collection.

LLDP resolves observed device/interface names, verified hostname/access aliases
and unique interface MACs, including dotted-MAC PortIDs and existing peers outside
the selected scope. Missing/ambiguous peers are reported; their hardware is not
invented. Fiber and ordinary network connections use LLDP.

SDK reads use `bittware_sdk_venv`, `fpga_bittware_sdk_root` and
`fpga_bittware_user` through shared discovery defaults. The GitLab runner venv/root
variables are fallbacks when configured. Override `bootstrap_bittware_*` only
when discovery needs a different environment. The collector checks installed
entrypoints, their Python dependencies and USB enumeration under that user;
installation remains in the provisioning role. It never runs pip or changes
firmware/ports. Review environment/USB failures before retrying.

FPGA interfaces come from actual QSFP headings, including Removed ports, rather
than a fixed count. Interface `fhs_port_observation` keeps observed presence and
fields separately from module identity. Populated pluggables retain vendor,
part/model, serial, revision, date, cable length and other reported fields in
native Inventory items/assets and `fhs_module_observation`; missing fields do not
clear known metadata. A clipped report does not imply absence. Observed module identity changes update the installed record in place.

FPGA DAC matching prefers complete serials, including suffixes, and the verified
FS vendor/part identities listed in the parser. The SDK VCSEL field alone cannot
classify a DAC. Repeated switch lane rows on one physical connector create one
native cable with multiple lane terminations; their shared transceiver module
records the connector association. No internal lane wiring is inferred.
Optical module serials never identify fiber cables.

For FS `QDD-400G-PC01`, the captured hardware reports complementary
`BASE-1` / `BASE-2` cable ends. After exact matches and explicit mappings, these
are paired automatically only when vendor/part match and the base resolves to
one FPGA connector and one switch connector. Both full serials remain recorded;
other products and suffixes have no automatic pairing rule.

An exceptional verified endpoint pair can be supplied in `bootstrap_dac_endpoint_pairs` with `vendor`, `part`,
`host_serial`, `switch_serial` and `evidence` (all nonempty strings). Both full
serials must resolve to one FPGA connector and one switch connector. Conflicting
rules, multiple physical connectors and occupied terminations are refused.
Existing real-to-real cables are never moved.

Verified DACs with an unresolved peer get a native cable to a dedicated interface
on `Unknown endpoint - <site ID>`, tagged `fhs-dac` and `endpoint-unresolved`.
The cable JSON field `fhs_dac_observation` keeps full serials, vendor, part and raw
connector properties (including reported length). Later unique opposite-end DAC
discovery replaces only that importer-managed placeholder endpoint, preserving
the cable ID; it also works when the ends are imported in separate runs.
Unresolved cables have Planned status; resolved cables are Connected. Empty
placeholder interfaces are retained. Optical transceivers alone create no cable.
The existing supported DAC product list and exact/FS paired-serial rules apply.
Ambiguous identities and occupied real endpoints remain untouched.
Review `topology_result.omissions` and
`topology_result.diagnostics`; repeated unchanged apply creates nothing.

`--tags facts` collects without topology API calls; `--tags compare` and `--check`
preview NetBox changes. Cable writes require the default run, `--tags apply` or `--tags cables`.
The credentials default is
`/provision/files.d/credentials/mid-cbf-hw-netbox.yml` for all entrypoints.

For private raw evidence, optionally set `bootstrap_discovery_capture_dir` to an
existing controller directory outside the repository with mode `0700`. Per-host
JSON files use mode `0600`, include source/time and raw probe output, and contain
no NetBox authentication. Check mode does not write captures. Keep these files
out of Git and public artifacts; each new capture replaces that host's file, so
use a separate directory per run. Parsed diagnostics are not raw captures.

Hardware assets use `netbox_inventory`; connections use native NetBox interfaces
and cables consumed by Topology Views. An Inventory API 404 indicates a plugin
prerequisite; an undrawn Topology Views page needs filters/search. Neither alone
establishes discovery success or a database cable count.

## Optional server placement and power

The importer reads `/etc/server-info.yaml` without rewriting it (`server_info_path`
can select another file). It supplies supplemental information not reported by
hardware, including placement, role and PDU assignments. Fields are optional;
role is assigned only when provided. Additional keys are retained by the metadata
reader; only explicitly mapped keys are applied to NetBox. Supported placement/power keys include:

```yaml
site: Example Site
role: FPGA_HOST_SERVER
location: Example Room
rack: Rack01
rack_unit: 12
power_ports:
  - name: PSU1
    pdu_serial: SYN-PDU-A
    pdu_port: "12"
  - name: PSU2
    pdu_serial: SYN-PDU-B
    pdu_port: "8"
```

`rack_unit` is a positive integer fitting the device type and rack. Existing
rack/position conflicts and overlapping devices are refused. An existing face is
retained; new positions use `netbox_rack_face_default: front`, as NetBox requires a
face. No new face/tenant/purpose metadata is collected.

Each inlet resolves its own PDU by exact serial and an existing native outlet by
exact name on that PDU. Names/serials must be nonempty strings; quote numeric
outlets. Missing/ambiguous identities, duplicate mappings and occupied
terminations fail before these placement/power writes. There is no PDU discovery
or control. Omitted new keys preserve existing placement/power records; an empty
power list does not remove cables. Run compare, inspect diagnostics, then apply
using the same selected scope.


## Collected information

Values below are recorded when available; missing observations preserve records.

| TeraBox / FPGA host | Information |
|---|---|
| Chassis | Hostname; override/FRU serial; manufacturer; actual FRU part/model; category tag |
| Placement | Server-info site, location, rack, explicit role; rack unit/face and explicit PDU inlet mapping |
| OS/resources | Distribution/version, architecture, logical CPUs, RAM MiB; common eligible whole-disk capacity GiB |
| Firmware | BIOS version and BMC firmware revision |
| FRU | Product serial/name/manufacture date/part/version/manufacturer; board serial/model/part/vendor/date; chassis serial/part/type; all FRU records/extras and identity provenance |
| DIMMs | Populated DDR5 detection, locator/bank/handle for naming, part and serial |
| NVMe | Physical-drive serial/model and an observed namespace path; serial deduplication |
| FPGA cards | SDK index, serial, part, board version, BMC firmware; explicitly supplied PCI endpoints and observed port names |
| NIC cards | VPD part/serial; PCI functions; interface names; driver/version; firmware; physical-port name; speed/duplex/link state |
| PSUs | Additional PSU FRU serial, manufacturer, part/model when reported |
| QSFPs | Connector, presence, vendor, part, serial and all reported EEPROM fields such as revision/date/length |
| Interfaces | Names, MAC/primary MAC, MTU, module associations, BMC management interface |
| Addresses | IPv4/IPv6 prefixes, selected primary IPv4, BMC out-of-band IPv4 |
| Cables | LLDP endpoints/identifiers; verified DAC serial evidence and endpoint-pair mappings; native network cables and explicit PDU cables |

| Cisco Nexus | Information |
|---|---|
| Chassis | Hostname, chassis serial, Cisco product ID/model, category tag; configured site/role |
| Software/firmware | NX-OS or kickstart version, BIOS version, optional EPLD report |
| PSUs/fans | Reported bays, product IDs, serials, descriptions and observed fan count |
| Transceivers | Vendor, product/part ID, serial, type, connector/lane names, presence and all scalar transceiver fields |
| Interfaces | Observed LLDP/transceiver interface names, connector/module associations, breakout lanes |
| Cables | LLDP local/remote endpoints and chassis identifiers; exact/verified FPGA DAC matches; native cable connections |

Per-DIMM capacity/vendor and per-NVMe capacity/firmware are not currently retained
as individual component fields. Nexus management discovery reads
`show interface mgmt0` (`nexus_management_command` override). `interfaces` ensures
the observed management interface; `ips`, default/apply also assign the observed
prefixed address and primary IPv4/IPv6. An `ips`-only run requires an existing
chassis and never creates one. No prefix or address is derived from the SSH target.
Missing, failed or ambiguous address observations and ownership conflicts preserve
existing addresses and primary selection, with diagnostics. Check mode, `compare`
and `facts` preview without writes. Switch interface MAC import remains unsupported.
Optical serials
alone never identify a fiber cable. Incomplete observations are reported rather
than creating a guessed peer or removing a missing component.

## Raw hardware reference

[capture_reference.yml](capture_reference.yml) is standalone. Set the two hosts
at the top (defaults `sys1391` and `nx00EF0`), SDK venv/root and optional SDK user.
Blank SDK settings resolve from the target inventory using the importer’s
variable precedence. The user falls back to the SSH user; an unresolved user is
reported instead of silently running SDK commands as root. The SDK runs with its
venv `bin` first in `PATH`, `BWSDK_ROOT`, and the C locale, set after switching
user. The resolved settings are included in the capture.
It needs Python 3 on Linux, sudo access, and the `cisco.nxos` and
`ansible.netcommon` collections on the controller. Existing inventory supplies
SSH addresses, users and credentials; the playbook also works with resolvable
hostnames and CLI credentials. It does not read NetBox credentials.

```sh
ansible-playbook -i YOUR_INVENTORY playbooks/netbox/capture_reference.yml -u YOUR_USER -K
```

Use your actual SSH inventory path. Do not pass `--limit`: the initial localhost
play defines the two capture groups. No importer files are required, so the YAML
can also be copied and run independently. No tools are installed or configured.

The controller receives `raw-reference/sys1391.json` and
`raw-reference/nx00EF0.json` beside the playbook (or set `capture_dir`). Each run
replaces these files. Files are private and gitignored. Linux command output is
kept verbatim in `collector.stdout` as JSON, with argv, exit status, stderr,
timeouts and timestamps; Ansible facts are also retained. Switch results retain
command text, raw stdout and unsupported-command errors. Missing tools do not
stop later probes. A connection or sudo failure is recorded where available.
Review the files before sharing: they contain real serials, addresses, network
neighbors, server-info and host facts, which can include environment details.

Linux captures FRU, DMI, BMC channels, PCI/VPD, USB, CPU/memory, block devices,
NVMe controller/namespace identity, OS/server-info, interface MAC/IP,
ethtool driver/link/permanent MAC/EEPROM, LLDP, and BittWare USB card/QSFP output.
NX-OS captures inventory, versions/EPLD, modules/environment, interfaces,
transceivers, LLDP and IP addresses. Unsupported variants
remain visible as errors. These captures are discovery evidence, not inventory
updates or proof of historical hardware replacements.

Reference coverage (raw samples; importer support is described separately above):

| Target | Device, module and connection evidence |
|---|---|
| Linux FHS | FRU system/board/PSU fields; full and importer-specific BIOS/memory DMI; NVMe controller/namespace identity; PCI IDs/VPD/drivers; interface PCI paths and physical port names; SDK card/port reports and explicit FPGA PCI map |
| Linux networking | Current/permanent MAC, IP/prefix, MTU and link attributes; LLDP details; decoded and hex module EEPROM, including reported cable type/length |
| NX-OS | Module/PSU/fan inventory, interface names/descriptions/MAC/status/capabilities, transceiver identity/diagnostics, IP addresses and LLDP peers |

The configured `server_info_path`, `bmc_lan_channel` and `hardware_command_path`
are honored. Set `bmc_channels` to a comma-separated list to sample additional
known LAN channels. Server-info retains rack/role metadata when present.
Connections use LLDP. PDU outlets and switch VLANs are outside this capture's
scope. FPGA USB indices still need matching evidence or an explicit map to
associate them with PCI functions; the capture retains that map when configured.

Syntax references: [Cisco NX-OS interface commands](https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus9000/sw/7-x/command_references/show_commands/b_N9K_Show_Commands_703i5x/b_N9K_Show_Commands_703i5x_chapter_01001.html),
[IPMI commands](https://github.com/ipmitool/ipmitool/blob/master/doc/ipmitool.1.in),
[LLDP commands](https://github.com/lldpd/lldpd/blob/master/src/client/lldpcli.8.in),
and [NVMe identify namespace](https://github.com/linux-nvme/nvme-cli/blob/master/Documentation/nvme-id-ns.txt).
Actual switch release, driver and hardware support is established by the returned
capture, including any command errors.

## Portable inventory JSON

[netbox_transfer.py](netbox_transfer.py) copies native inventory through the REST
API using the existing Python requirements. It does not migrate the database,
history, users, permissions, credentials or plugin objects. Review the private
report: exit `2` means incomplete/unsupported data, `1` means an input/API failure.
A successful command alone is not an all-field migration guarantee.

```bash
python3 playbooks/netbox/netbox_transfer.py export \
  --vars /private/old-netbox.yml --file /private/inventory.json \
  --device switch01 --device pdu01 --device server01 --report /private/export-report.json
python3 playbooks/netbox/netbox_transfer.py import \
  --vars /private/new-netbox.yml --file /private/inventory.json \
  --dry-run --report /private/preview.json
python3 playbooks/netbox/netbox_transfer.py import \
  --vars /private/new-netbox.yml --file /private/inventory.json \
  --report /private/import-report.json
```

Vars use `netbox_url`, `netbox_token` and `netbox_validate_certs` (fallback
`netbox_validate_certs_default: true`, matching the playbooks). URLs may include
a deployment prefix. Values must be resolved YAML, without Jinja expressions.
Tokens use `Bearer` for `nbt_` tokens and `Token` otherwise. Vault files use
`ansible-vault view`; inline `!vault` uses Ansible's DataLoader. Pass
`--vault-password-file /private/password` or `--vault-id name@/private/password`;
Ansible must be available in the same environment. No password/token arguments.
Exports and reports require new paths and are created mode `0600`; their parent
folder should be private too. Stdout contains counts, not inventory or payloads.

Without `--device`, export scans supported native endpoints. Selection includes
connected components/cables and their dependencies, potentially including other
devices. Inspect the file before import. Sites, locations, racks, manufacturers,
roles, device/module types and component templates precede installations through
portable natural keys. Primary IP/MAC and other forward references are deferred.
Inventory items, interfaces, addresses, PSU ports/outlets, cable terminations,
tags and custom-field definitions/values use destination IDs after resolution.
JSON custom fields and local context data remain literal nested JSON. Object
custom fields require a supported target type; unsupported fields are reported.

Import creates missing records and PATCHes matching records. Names are scoped
by parent/site where applicable; devices match site/name, modules match their
bay, IPs match VRF/address, MACs match address and cables match both endpoint
sets. Ambiguity is an error. No DELETE operations occur. Fields absent from the
file preserve destination values. Explicit null/empty fields are submitted to
the API, subject to its validation; lists replace supplied lists. Supplied
custom-field names merge with destination values; `{}` requests all values be
cleared. An occupied IP/MAC cannot be detached or reassigned, and occupied cable
endpoints are preserved. Unprofiled NetBox 4.7 cables emit null `profile` but
reject it on input; creation omits that default, while clearing an existing
profile remains an API error. Reruns retry failures and converge on supported
fields; imports are partial operations, without rollback.

The file records source versions and read-only/generated fields. Destination
OPTIONS must expose writable metadata; version/plugin differences are reported.
Unknown nested relationships and numeric ID fields require explicit adapters and
are omitted with a report, never copied as source IDs. Inventory plugin assets,
item types/groups, asset roles, suppliers, purchases, deliveries and audit objects
are explicitly unsupported. Other plugins, virtualization, wireless, circuits,
configuration templates and unregistered relationship targets are unsupported.
Free-text/JSON may itself contain private material: these files need the same
protection as inventory backups. An export refuses the active API token if found
in source metadata; this is not a general secret scanner.
