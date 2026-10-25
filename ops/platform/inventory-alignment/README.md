# Inventory alignment checks

Pinned NetBox `4.7.0` + MIT Inventory `2.7.1`; shared image/configuration in the
[portable chart](../../../platform/charts/fhs-platform/README.md). The chart uses
the public base image and installs the pinned plugin at startup; the legacy lab
[deployment entrypoint](../deploy.sh) uses the optional prebuilt image.
Never use the default Kubernetes context (`monitoring`) for these tests.

```bash
python3 -m unittest discover -s ops/platform/inventory-alignment -p 'test_*.py' -v
python3 -m unittest discover -s ops/platform/umbrella -p 'test_*.py' -v
```

After the parent activates the delivered chart on existing cluster `fhs-test`,
run native importer acceptance with an isolated synthetic namespace/database:

```bash
python3 ops/platform/inventory-alignment/acceptance.py \
  --credentials /private/alignment.json --report /tmp/alignment-acceptance.json
```

The mode-0600 input JSON contains `url` (NetBox base, including prefix) and
`token`. Requirements: `ansible` and `ansible-playbook` on PATH, PyYAML for the
harness and `requests` in the module interpreter;
set `FHS_ANSIBLE_PYTHON` if it differs from the Python running acceptance.
The harness uses native Ansible module packaging/CLI and real REST, never fake
Ansible imports. It retains uniquely named `SYN-ALIGN-*` fixtures for inspection.
It covers chassis serial/hostname identity, FPGA/NIC/component/Nexus asset
repeat/replacement/removal, uncabled interface ID retention, journals, real
change logs and manual standalone DAC quarantine without inventing a peer.
It also executes actual compare tasks in check mode with existing IP/MAC owners
before a chassis rename, and tests real cabled replacement refusal.
No physical server or switch is contacted.

The full umbrella render remains a separate check. A resource-limited scoped
NetBox + backing-service activation proves those components only; do not report
monitoring/logging capacity or a full-stack deployment from that run. Record
runtime plugin configuration, image, migrations/readiness, API status, prefixed
static HTTP paths, media affinity and history retention with the report.

The routing/task-flow tests require real Ansible and loopback permission; without
Ansible they explicitly skip. No skip substitutes for runtime acceptance.

See [screen/baseline](HANDOFF.md), [official source review](UPSTREAM.md) and
[actual validation](VALIDATION.md).

## Optional IPMI FRU

`test_fru.py` covers distinct identities, hardware before bootstrap fallbacks,
placeholders/date models, missing/failed/partial records, selected/multiple FRUs,
vendor-scoped types and corrections retaining chassis asset IDs.
The native FRU task checks use fake local commands and synthetic REST.
`test_routing.py` verifies that a failed host does not abort other hosts/families.
`fixtures/fru.txt` follows a user-supplied FRU photo's field structure; serials,
product part number and extra metadata are synthetic. Manufacturer and board
model names retain the distinct system/board vendors. The private image is not
stored here.

Run the actual identity/compare/apply tasks against the isolated chart NetBox:

```bash
python3 ops/platform/inventory-alignment/acceptance_fru.py \
  --credentials /private/alignment.json --report /tmp/fru-acceptance.json
```

Use the same dependencies/private URL-token JSON as `acceptance.py`, plus the
NetBox collection and `pynetbox` from the importer requirements. Only fake local
IPMI/DMI commands are executed. Native acceptance also corrects manufacturer and
model with stale bootstrap fallbacks, then checks repeat-import stability and
retained chassis asset IDs. The run retains unique `SYN-FRU-*` objects and a
sanitized last-task log beside the report. It does not establish physical BMC
access or firmware behavior.

`test_startup_plugin.py` checks all three consumers, non-root package volumes,
pinned hash enforcement, offline prebuilt detection and installation failure.
The launcher regression also verifies static collection before serving.

## LLDP and DAC topology

[Issue #15](https://github.com/DragonLord-64/experimental-fhs-baremetal/issues/15).
`test_topology.py` covers exact serials, duplicate breakout reports, occupied
ports, contradictory LLDP/serial evidence, Linux JSON shapes and Nexus LLDP/MAC
resolution. Run the native collector/module check against the same isolated
chart instance:

```bash
python3 ops/platform/inventory-alignment/acceptance_topology.py \
  --credentials /private/alignment.json --report /tmp/topology-acceptance.json
```

Retains two uniquely named `SYN-TOPO-*` devices and their imported cable.
`probe_topology.py` runs in that NetBox's Django shell with
`FHS_TOPOLOGY_PREFIX` set to the report's prefix. It checks that the imported
connection appears in the authenticated Topology Views graph; its login session
is rolled back. Both plugins must be active. Hardware commands use synthetic
read-only executables; physical LLDP/EEPROM access remains unverified.

## Discovery completion

[Issue #16](https://github.com/DragonLord-64/experimental-fhs-baremetal/issues/16).
The controller runs one entrypoint; implementation workers do not run it:

```bash
python3 ops/platform/inventory-alignment/acceptance_discovery.py --dragonvm \
  --report /tmp/fhs-discovery-completion-acceptance.json
```

It inspects preserved services/pipeline processes first, then uses retained
release `fhs-inventory-alignment` on explicit context `fhs-test`. No cluster
creation, deployment or lifecycle tests are included. Missing chart/services,
plugins, credentials, dependencies or skipped fixtures fail explicitly. Existing
protected credentials are consumed in memory; a temporary loopback forward is
closed afterward. Source transfer excludes private original images and runs.

The harness runs real Ansible syntax/routing and focused discovery contracts,
then the actual Nexus tasks through a synthetic NX-OS command boundary, SDK
collector tasks with synthetic installed tools, and native importer API checks.
It requires all seven representative LLDP links, dynamic/Removed QSFP ports,
Inventory metadata/assets, one physical cable for repeated breakout lanes,
exact/explicit DAC identities, conflict preservation, partial/failed reads,
read-only modes, rack placement and distinct-PDU inlet cables. Native failure
coverage is limited to invalid placement, a missing PDU and an occupied outlet;
local contracts retain the identity/schema cases. SDK native coverage verifies
the configured tools, environment and effective user without repeating a failure
matrix. Authenticated
Topology Views must contain each imported native network cable; the Inventory
asset page and identity must work. Repeated apply must be unchanged.

A pass requires every stage, not just unit tests or cable count. Reports publish
selected synthetic assertions; mode-0700 evidence directories retain private
logs and fixture data. Synthetic objects remain for review under a unique
`SYN-DISC-*` prefix. This does not establish physical hardware behavior.
See [fixture provenance](fixtures/discovery/README.md) and
[validation status](VALIDATION.md#discovery-completion--controller-pending).
