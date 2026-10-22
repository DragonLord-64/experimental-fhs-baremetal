# Infrastructure dashboards

Six native Grafana views adapted from the user's dashboard prototypes:
nine physical 42U rack elevations, 24×27 mesh, compact FHS components,
32-port/four-interface switch, interface details, and VLAN allowance/routes.

```bash
python3 platform/grafana_dashboards/generate.py
python3 -m unittest discover -s platform/grafana_dashboards/tests -v
```

`exact.py` adapts the geometry in `references/`; its manifest records source
paths and SHA256 hashes. The original checkout is never changed or executed.
`generate.py` retains the native metric/query helpers and portable UID links.
Generated JSON uses classic schema 39 and Grafana 13.2.3.

## Inventory and observations

Full display: 24 VCC and 27 FSP. Racks 1–6 each contain four VCC and three FSP;
racks 7–9 contain three FSP. Each VCC has one FHS and one switch; each FSP
has four FHS and one switch. Placement is explicitly SYNTHETIC: switches 1U,
servers 2U; these heights are illustrative, not verified TeraBox dimensions.
Canvas placement is independent of observation availability.

Only 4 VCC/3 FSP are emulated: 16 FHS, 7 switches, 12 mesh links. Nothing here
expands emulation. `deployed-interfaces.json` records the configured lab
interfaces from the reduced emulator topology. Gray **NOT DEPLOYED / ND**
means absent inventory; **TELEMETRY MISSING / ?** means deployed without
observations. Observed **Down** is red. Static presentation constants classify
inventory/unknown states only; they never supply healthy readings or rates.

FSP 1's four FHS have missing telemetry. FSP 2/FHS 1 has one PSU 1 fault and
aggregate Degraded status. VCC 1 eth1/1/3 and FSP 3 eth1/1/1 are one broken
mesh link. Other observed links are Up. Some native FHS readings are dropped
by the current scrape filter; affected components remain Unknown.

Switch overview retains 128 slots, shows observed link states, and provides
selected-port transceiver/optical and chassis/PSU/fan sections. Supplied Nexus
chassis metric names are queried; absent sensors and unsupported optic/fan
fields remain Unknown. Link Up never establishes parent hardware health.
No VLAN configuration is available: the two tables retain explicit inventory
rows, while allowances, match counts and directed routes remain unavailable.
No invented VLANs, inverse routes, traffic rates or healthy states are used.

## Import and navigation

Import all six files in `generated/` into the owned folder `fhs-infra-issue2`.
UIDs are `fhs-infra-rack`, `fhs-infra-mesh`, `fhs-infra-server`,
`fhs-infra-switch`, `fhs-infra-interface`, `fhs-infra-vlan`.
The obsolete `fhs-infra-fhs` UID is not used.

Destination selectors show readable titles and retain stable UID values.
Links carry datasource, actual selector names, time and selection context.
Unrelated source selectors are hidden on each view. The full unit/switch
inventory remains selectable without depending on live telemetry labels.
Datasource/job/identity labels need adaptation for production; the emulator
contract is not a claim of production compatibility.

See [supervisor operations](SUPERVISOR.md) and [validation](VALIDATION.md).
Imports use bounded ownership discovery and optimistic ID/version checks;
foreign-folder conflicts fail closed. Credentials and browser sessions remain
outside Git. Independent source/visual review precedes commit and push.
