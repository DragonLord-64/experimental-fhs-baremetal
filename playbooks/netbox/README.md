# NetBox import and export

Run from `/provision` with `requirements.yml`, `requirements.txt`, protected
NetBox variables and a selected inventory scope. See the
[development playbooks](../../docs/src/playbooks/development.md) for commands,
asset reconciliation and Nexus routing.

Change `netbox_credentials_file` in [defaults.yml](defaults.yml) to set
one credentials path for all import plays and the Bifrost export. The same file
holds SDK/NIC discovery, topology commands, API retries, certificate validation,
site/role defaults and Bifrost export settings. Override it
per run with `-e netbox_credentials_file=/private/netbox.yml`.

## Linux system identity

`netbox_import.yml` reads Linux facts, `/sys/class/dmi/id/chassis_serial` and local
`ipmitool fru` over the configured connection. Discovery uses the same privilege
settings as BIOS/BMC reads. No IPMI network credentials are added or tool installed.
`facts`, `compare` and check mode keep these probes read-only.

`system_fru_id` selects the system record (default `0`; older
`motherboard_fru_id` remains an alias). All FRU records are kept separately in
`fru_inventory`; other FRUs do not fill the selected record's missing fields.
Failed reads and missing/duplicate record IDs do not supply FRU identity fallbacks.

| NetBox destination | Discovery |
|---|---|
| Device serial / chassis asset | `bootstrap_chassis_serial`, DMI chassis serial, selected FRU Chassis Serial |
| Device type manufacturer | `bootstrap_manufacturer`, DMI system vendor, FRU Product Manufacturer |
| Device type model | `bootstrap_device_type`, DMI product name, usable FRU Product Name, Product Part Number, Chassis Part Number |
| `product_*` device fields | DMI product fields where available, otherwise corresponding FRU fields; serial/version remain product identity |
| `motherboard_*` device fields | DMI board vendor/name/serial, otherwise FRU Board Mfg/Product/Serial; FRU part number and manufacture date |
| Motherboard inventory item / asset | Only with observed board manufacturer, model and serial; board model identifies its type; part number is set only when observed |
| `chassis_part_number`, `chassis_type` | Selected FRU Chassis Part Number/Type |
| `hardware_identity_sources` | Per-field source, including FRU ID and label |
| `fru_inventory` | Records keyed by FRU ID, with description and fields including additional product/board metadata |

Empty values and OEM placeholders are omitted. Date-shaped strings are retained
as observations but cannot identify a model. Board and product serials never
substitute for a chassis serial. FRU Product Version is separate from BIOS
(`dmidecode --type bios`) and BMC firmware (`ipmitool mc info`).

Missing FRU data is normal. New optional fields stay empty; existing fields,
provenance, FRU records and assets survive partial reads. A missing chassis
serial permits hostname-based device updates without creating/reassigning an
asset; it cannot establish a rename. NetBox requires a device type: new devices
without manufacturer/model are reported and skipped until verified overrides
are supplied. A discovered identity that conflicts with an existing chassis
serial/type still requires review. Records imported previously with a product
serial in the chassis field are not silently rewritten.

FRU discovery never enables absence removal. Motherboard reconciliation always
uses an incomplete scope; DDR5/NVMe, FPGA, NIC and Nexus completeness rules remain
separate. Keep discovery output private because it contains hardware identifiers.

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
clear known metadata. A clipped report does not imply absence. Existing module
replacement conflicts require review.

FPGA DAC matching prefers complete serials, including suffixes, and the verified
FS vendor/part identities listed in the parser. The SDK VCSEL field alone cannot
classify a DAC. Repeated switch lane rows on one physical connector create one
native cable with multiple lane terminations; their shared transceiver module
records the connector association. No internal lane wiring is inferred.
Optical module serials never identify fiber cables.

There is no automatic suffix stripping. An exceptional verified endpoint pair
can be supplied in `bootstrap_dac_endpoint_pairs` with `vendor`, `part`,
`host_serial`, `switch_serial` and `evidence` (all nonempty strings). Both full
serials must resolve to one FPGA connector and one switch connector. Conflicting
rules, multiple physical connectors and occupied terminations are refused.
Existing cables are never moved. Review `topology_result.omissions` and
`topology_result.diagnostics`; repeated unchanged apply creates nothing.

`--tags facts` collects without topology API calls; `--tags compare` and `--check`
preview NetBox changes. Cable writes require the default run or `--tags apply`.
The credentials default is
`/provision/files.d/credentials/mid-cbf-hw-netbox.yml` for all entrypoints.

For private raw evidence, optionally set `bootstrap_discovery_capture_dir` to an
existing controller directory outside the repository with mode `0700`. Per-host
JSON files use mode `0600`, include source/time and raw probe output, and contain
no NetBox authentication. Check mode does not write captures. Keep these files
out of Git and public artifacts; each new capture replaces that host's file, so
use a separate directory per run. Parsed diagnostics are not raw captures.

See [fixture provenance and limits](../../ops/platform/inventory-alignment/fixtures/discovery/README.md)
and the [controller acceptance](../../ops/platform/inventory-alignment/README.md#discovery-completion).
Hardware assets use `netbox_inventory`; connections use native NetBox interfaces
and cables consumed by Topology Views. An Inventory API 404 indicates a plugin
prerequisite; an undrawn Topology Views page needs filters/search. Neither alone
establishes discovery success or a database cable count.

## Optional server placement and power

The importer reads `/etc/server-info.yaml` without rewriting it (`server_info_path`
can select another file). Existing files still require site, role, location and
rack. New keys are optional:

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
