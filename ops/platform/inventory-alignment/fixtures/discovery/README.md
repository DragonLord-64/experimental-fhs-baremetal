# Discovery evidence

Representative, sanitized fixtures for [issue #16](https://github.com/DragonLord-64/experimental-fhs-baremetal/issues/16).
Original seven JPEGs and SHA-256 index remain in the private pipeline evidence
folder; no images or identifier crosswalk are published. All seven were read.
The five latest images provide hardware evidence; earlier images show Inventory
API 404 (plugin prerequisite) and `draw_init=False` (undrawn filter state).
The sparse graph is an observed outcome, not a database cable count.

- `nexus-*-lldp.txt`: the two photographed tables, three and four rows. Device
  aliases and MACs are consistently replaced. Local and remote port spelling,
  separate management links, hold times and capabilities are retained.
- `linux-lldp.txt`: access alias `SYN-ACCESS-A` differs from actual hostname
  `SYN-HOST-A`. Switch chassis/MgmtIP use synthetic MAC/documentation address.
  The last interface is clipped; its neighbor details are not fabricated.
- `qsfp-photo.txt`: actual field layout and part strings; serials map to
  `SYN-CABLE-B-2` and `SYN-CABLE-C-1`. The second port ends where the photo ends.
  Missing presence and telemetry are deliberately missing.
- `qsfp-official.txt`: official `development2` `4533a85`,
  `playbooks/development/output-samples.md`; paired `SYN-CABLE-A-1/-2` and a
  Removed QSFP2. The original suffix relationship and formatting are retained.
- `*-lldp.json`: **synthetic JSON encodings**, not photographed command output.
  They exercise supported lldpcli/NX-OS table shapes at the command task boundary.
- `nexus-*-inventory.json`, `*-version.json`, `*-optics.json` and `cards.txt`:
  **synthetic supplemental reports**. Breakout repeated rows follow official
  `playbooks/development/topology-discover-strategy.md`; B-2 is an exact match,
  C/C-1 is deliberately unresolved without an explicit verified endpoint pair.
  Synthetic distinct card serials permit native asset lifecycle checks. These
  reports are not claimed as fields visible in a photo.

Aliases are `SYN-NEXUS-A/B`, `SYN-MGMT`, `SYN-HOST-A/B/C/D` and
`SYN-ACCESS-A`. Host port MACs are `02:00:00:00:00:01` through `:04`;
switch A chassis is `02:00:00:00:10:01`. No mapping to private originals is stored.
Retain the synthetic run prefix consistently across JSON, command output and API
objects. The controller retains private command logs and publishes selected
assertions only.

FS identifies `QDD-400G-PC01` as a passive copper cable in its
[product data sheet](https://resource.fs.com/mall/resource/400g-qsfp-ddosfpqsfp112-cable-and-transceiver-modules-data-sheet.pdf).
The SDK's VCSEL field alone cannot override vendor/part identity. The official
examples do not establish a collision-safe universal suffix rule. This importer
therefore requires exact serials or explicit full endpoint pairs with evidence.

Breakout model: one native cable has multiple observed lane interface
terminations on the switch side and one physical FPGA interface on the other.
The shared native transceiver module associates those lanes with one physical
connector/module bay; it is not several DAC cables. No channel numbering or
internal lane wiring is inferred. NetBox supports multiple terminations
([cable model](https://netbox.readthedocs.io/en/stable/models/dcim/cable/)); actual
API, Inventory and Topology Views compatibility must pass controller acceptance.
