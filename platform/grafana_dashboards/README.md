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

Full display: 24 vccu and 27 fspu. Racks 1–6 each contain four vccu and
three fspu; racks 7–9 contain three fspu. Each vccu has one FHS and one switch;
each fspu has four FHS and one switch. Synthetic placement uses 1U devices
and one empty U between logical unit blocks. Mixed racks span 29U, leaving
13U above; fspu-only racks span 17U. All nine elevations retain 42U numbering.

Only 4 vccu/3 fspu are emulated: 16 FHS, 7 switches, 12 mesh links.
`deployed-interfaces.json` records configured lab interfaces. Status vocabulary
is `ok`, `degraded`, `fault`, `unknown`, `not deployed`. `unknown` means deployed
without sufficient observations; `not deployed` means absent inventory.
Observed link down is `fault`; it does not establish parent hardware health.
Native metric names and raw selector values remain compatible; selectors show
canonical lowercase identities such as `fspu1-fhs1`.

fspu1's four FHS have missing telemetry. fspu2-fhs1 has one PSU1 fault and
aggregate `degraded` status. vccu1 eth1/1/3 and fspu3 eth1/1/1 are one broken
mesh link. These are scenario expectations, pending fresh supervisor evidence.
The catalog has 21 components: all 16 hosts require 336 selections, including
84 on missing hosts. Requested 168 would cover eight hosts only.
`evidence_plan.py` enumerates every selection and its primary reading queries;
unsupported observations remain unknown and must be counted separately.

Switch overview retains 128 slots, shows observed link states, and provides
selected-port transceiver/optical and chassis/PSU/fan sections. Lane identities
L1–L4 are separate from status; ND / ? mean not deployed / unknown. Parent
status is independent and shown in full with high contrast. Supplied Nexus
chassis metric names are queried; absent sensors and unsupported optic/fan
fields remain `unknown`. Link `ok` never establishes parent hardware health.
No VLAN configuration is available: the two tables retain explicit inventory
rows, while allowances, match counts and directed routes remain `unknown`.
Mesh throughput shows separate RX/TX 5m counter rates from the selected vccu
endpoint, using native `nexus_interfaces_octets` dn In/Out counters and LLDP
peer identity. The peer endpoint is not counted again. Bytes/s convert by
8/1e9 to Gbit/s with nine decimals; missing rates stay unknown even when a
link is down. The sanitized observed contract had 112 valid rate series;
1016.9491525423729 bytes/s is about 0.000008136 Gbit/s per direction.
Capacity and utilization remain unknown without observed configured/negotiated
capacity. No invented VLANs, inverse routes, traffic rates or healthy states are used.

## Import and navigation

Import all six files in `generated/` into the owned folder `fhs-infra-issue2`.
UIDs are `fhs-infra-rack`, `fhs-infra-mesh`, `fhs-infra-server`,
`fhs-infra-switch`, `fhs-infra-interface`, `fhs-infra-vlan`.
The obsolete `fhs-infra-fhs` UID is not used.

Destination selectors show readable titles and retain stable UID values.
Links carry datasource, actual selector names, time and selection context.
The peer table retains table-hidden `peer_role` / `peer_number` components
and builds native URL identities with literal `Unit` and `-switch`. These
components avoid entity-name mappings; visible peer names remain lowercase. Supervised Grafana href/click validation is
required to verify retained frame context.
Unrelated source selectors are hidden on each view. The full unit/switch
inventory remains selectable without depending on live telemetry labels.
Datasource/job/identity labels need adaptation for production; the emulator
contract is not a claim of production compatibility.

See [supervisor operations](SUPERVISOR.md) and [validation](VALIDATION.md).
Imports use bounded ownership discovery and optimistic ID/version checks;
foreign-folder conflicts fail closed. Credentials and browser sessions remain
outside Git. Independent source/visual review precedes commit and push.
