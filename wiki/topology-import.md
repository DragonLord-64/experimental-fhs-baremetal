# NetBox topology import

Current accepted behavior: [working hardware import baseline](netbox-import-baseline.md).
The dated records below retain earlier decisions and validation boundaries; the
baseline supersedes their identity, suffix-matching and removal policies.

[Issue #15](https://github.com/DragonLord-64/experimental-fhs-baremetal/issues/15)
adds topology to the [unified importer](../playbooks/netbox/README.md#topology).
Source: official `development2`, commit `dc08629`,
`playbooks/development/topology-discover-strategy.md`; Cisco's
[LLDP JSON contract](https://developer.cisco.com/docs/cisco-nexus-9000-series-nx-api-cli-reference/latest/lldp-commands/).

Linux/FHS and NX-OS keep separate collection strategies behind one entrypoint.
After inventory import, exact LLDP names/unique interface MACs and unique DAC
serial pairs produce native NetBox cables. Inventory assets remain under the
Inventory plugin; Topology Views reads the native connections. See the
[asset/replacement policy](resource-layout.md#import-decision--2026-10-22) for
serial identity, retained assets and cabled-removal refusal. No LLDP daemon,
port configuration or FPGA register is changed.

Serial suffixes are significant. The upstream example contains mismatched
suffixes and repeated switch breakout serials: those observations are unresolved,
not proof of a unique pair. Missing or conflicting endpoints preserve cables.
Other switch operating systems need a collector; they are not silently treated
as supported NX-OS devices.

## Observed validation — 2026-10-25

Existing `fhs-test`, scoped chart release/namespace `fhs-inventory-alignment`:
NetBox 4.7.0, Inventory 2.7.1 and Topology Views 5.0.0. Upgraded the delivered
chart using retained private values, Secrets and PVCs; web and worker Ready.

- 64 importer tests passed (61 in the suite, three deployment checks rerun after
  supplying omitted test dependencies); both importer syntax checks passed.
- Native Linux topology tasks collected synthetic NIC/FPGA EEPROM output;
  native module preview/apply/repeat passed and persisted one cable with both
  endpoints. Run `SYN-TOPO-5474f85c`.
- That exact imported connection appeared in the authenticated Topology Views
  graph. Existing Inventory asset regression: 69 checks, `SYN-ALIGN-976bf183`.

Reports and logs remain private on dragonvm in
`/home/dragon-lord/fhs-topology-20261025/runtime/`. The first topology attempt
hit the chart rollout's expired port-forward; reconnecting after readiness fixed
it. Physical switch/FPGA/NIC discovery is not established by synthetic fixtures.
See [test entrypoints](../ops/platform/inventory-alignment/README.md#lldp-and-dac-topology).

## Completion update — 2026-10-25

[The discovery extension](../playbooks/netbox/README.md#topology) now preserves
observed empty QSFP interfaces and module metadata, groups repeated breakout
lanes by physical connector and resolves verified LLDP aliases/MACs. Full DAC
serials remain preferred; differing endpoint serials require an explicit
vendor/part/full-serial pair with evidence rather than suffix stripping.
Optional server metadata adds rack-unit placement and independent PDU mappings.

[Focused native acceptance](../ops/platform/inventory-alignment/VALIDATION.md#discovery-completion--accepted-2026-10-25)
passed with screenshot-derived sanitized fixtures on the retained chart.
This supersedes the earlier duplicate-breakout limitation above; physical
hardware behavior remains unverified.
