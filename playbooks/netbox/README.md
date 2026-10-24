# NetBox import and export

Run from `/provision` with `requirements.yml`, `requirements.txt`, protected
NetBox variables and a selected inventory scope. See the
[development playbooks](../../docs/src/playbooks/development.md) for commands,
asset reconciliation and Nexus routing.

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
