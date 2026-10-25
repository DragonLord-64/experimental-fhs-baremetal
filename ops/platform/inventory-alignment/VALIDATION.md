# Inventory alignment validation

2026-10-24, private issue [#8](https://github.com/DragonLord-64/experimental-fhs-baremetal/issues/8).
Existing dragonvm Kubernetes context `fhs-test`; default `monitoring` preserved.
No physical server/switch or production inventory was contacted.

## Actual deployments

Built the shared pinned NetBox `4.7.0` / MIT Inventory `2.7.1` image and loaded
`fhs/netbox-inventory:4.7.0-2.7.1` into existing minikube `fhs-test`.
That prebuilt image is not published to an external registry. The subsequent
startup-install change below supersedes the portable chart's build prerequisite;
the [prebuilt recipe](../../../platform/charts/fhs-platform/netbox-image/README.md)
remains available for legacy/offline use.

- Main legacy release `netbox`, namespace `fhs-platform`: backed up PostgreSQL,
  Secrets and Helm configuration privately, then upgraded only NetBox with
  canonical + dragonvm values. Migrations and bootstrap succeeded. Web, worker
  and housekeeping specify the shared image; web/worker Ready, zero restarts.
  Existing **186 devices** preserved. Effective serial/tag synchronization true;
  change-log retention 90 days.
- Fresh delivered umbrella release/namespace `fhs-inventory-alignment`, prefix
  `/alignment`: actual bundled chart, separate PostgreSQL/Valkey/media and
  credentials. A private post-renderer selected only NetBox and its backing
  services to fit available lab resources; retained static lab PVs were supplied
  separately. Migrations, web and worker readiness succeeded. This proves the
  chart's NetBox integration, not an all-components platform deployment.
- Main `/netbox/` and candidate `/alignment/netbox/` login plus the four actual
  referenced CSS/JS paths returned HTTP 200. Runtime plugin version/sync settings
  were read back. Web/worker share node `fhs-test`; multi-node CSI attachment
  behavior is not established by a single-node run.
- Main read-only [resource check](../netbox-resource-test.py): **62 API requests**
  with a concurrent Django read, 19 overlapping pairs, 186 devices, unchanged
  pod UID/restarts and zero OOM events. Web limit 2 GiB, two workers; measured
  cgroup peak 889,077,760 bytes. Elasticsearch/Kibana remain at zero replicas.

Private backup: `/home/dragon-lord/fhs-netbox-alignment-backup-20261024` on
Dragonvm (database dump and Secrets, mode 0600). Do not commit these files.
Runtime reports/fixtures: `/home/dragon-lord/fhs-inventory-alignment-20261024/runtime`.
No database reset or host shutdown was required.

## Importer evidence

Initial native Ansible module CLI acceptance against the delivered candidate
passed **59 checks**: stable serial assets, chassis hostname rename, FPGA/NIC,
DDR5 inventory items and Nexus local modules, replacement/removal, incomplete
scope preservation, interface IDs, parent journals, real asset change logs and
standalone DAC stored/used/faulty transitions. Later review found gaps outside
that initial module-only boundary. The final frozen-source native run passed
**69 checks**, adding actual comparison-task execution before rename with
existing assigned IP/MAC, check-mode no-write confirmation, real cabled FPGA
replacement refusal and invalid-serial complete-scan preservation. Synthetic run
`SYN-ALIGN-c5561be3` remains in the separate candidate database for inspection.

The public entrypoint's routing tests execute real Ansible on a synthetic mixed
inventory, substituting family payloads and transport only. Native acceptance
uses actual packaged custom modules and REST, with uniquely named synthetic
fixtures. These are separate boundaries. Full public-playbook discovery on real
FHS/Nexus hardware, ingress/TLS and a complete platform deployment remain
unverified. No hardware behavior is inferred from fixture success.

## Review corrections

Fresh review reproduced three failures missed by the initial suites: partial
FPGA SDK headings could authorize absence deletion; hostname-based MAC/IP guards
blocked a serial-matched chassis rename; new reconciliation tasks omitted API
retry wiring. A fresh implementation worker corrected these with focused regressions.
The final alignment suite passed **38/38**, including real Ansible routing and
task-body checks for serial-matched rename/conflicts, transient HTTP 503 retries
on all four new reconciliation tasks, permanent-error/retry-budget controls,
partial SDK preservation and explicit empty removal. No tests skipped in that
run. Ten umbrella checks also passed. The user requested the human review step
in place of a further automated review round; no additional review pass is claimed.

## Optional FRU identity — 2026-10-24

Private issue [#10](https://github.com/DragonLord-64/experimental-fhs-baremetal/issues/10).
The [FRU fixtures and entrypoint](README.md#optional-ipmi-fru) use synthetic
serials/part/extra metadata; the user's private photo is not committed.

- Local alignment suite: **50/50**, no skips, with real Ansible routing/task
  execution. Both importer syntax checks passed in the lab Ansible runtime;
  Python compilation and `git diff --check` passed. Six source-boundary checks
  passed after integration with the concurrent source/lab reorganization.
- Actual identity/compare/apply tasks against delivered-chart NetBox `4.7.0` /
  Inventory `2.7.1`, namespace `fhs-inventory-alignment`, context `fhs-test`:
  **16 checks**, run `SYN-FRU-0700dc6b`. Distinct chassis/product/board identities,
  board manufacturer/model, separate firmware/product version, JSON provenance
  round-trip, unchanged full rerun, partial updates, failed/missing IPMI, existing
  asset preservation, no-type skip and empty identities on new no-IPMI devices.
- Final native asset regression: **69 checks**, run `SYN-ALIGN-ba92a67f`, including
  chassis rename/IP/MAC guards, cabled refusal, FPGA/NIC/component/Nexus
  replacement/removal, retained asset IDs, journals and real change logs.

Reports and retained synthetic fixtures are on dragonvm under
`/home/dragon-lord/fhs-fru-20261024/` (`fru-acceptance.json`, sanitized last-task
log, `asset-regression-final.json`). Existing lab services were inspected before
execution. No cluster recreation, production inventory or physical hardware
access occurred. Fake local commands exercise collection/task wiring, not actual
IPMI access or physical firmware behavior.


## Automatic plugin installation — 2026-10-24

User reported hardware `ImagePullBackOff`, then requested a simpler plugin-only
installation. The previous custom image was not published; target pod Events
were not supplied, so that target-side cause remains unconfirmed. The portable
chart now uses the pinned public NetBox image and installs Inventory `2.7.1`
automatically into non-root per-pod volumes, with wheel hash verification.
A matching prebuilt installation skips downloading. Pods need PyPI HTTPS access
when the selected image does not contain the package.

Actual existing `fhs-test` lab evidence:

- A UID-1000, read-only-root probe installed the pinned wheel on the stock image.
- Upgraded only scoped release `fhs-inventory-alignment`, revision 3. Web and
  worker Ready on the public image; Inventory `2.7.1`, sync enabled, management
  commands work without extra environment arguments. Housekeeping configuration
  was rendered/checked; no housekeeping job was executed.
- Replaced the owned web pod; the new UID reinstalled the package automatically.
  Nine devices and 48 assets remained before/after; web/worker restart counts zero.
- API status and login plus four referenced JS/CSS assets returned HTTP 200 at
  `/alignment/netbox/`. The legacy main instance remains Ready with 186 devices;
  it was not upgraded or reset by this test.
- Four installer regressions, ten umbrella tests, six source-boundary tests,
  three legacy/deployment tests and chart lint pass. Tests verify package failure
  stops startup, all consumers load the package, optional prebuilt mode skips
  network installation, and initialization/static serving are preserved.

Private runtime evidence remains under
`/home/dragon-lord/fhs-inventory-alignment-20261024/runtime/`, including
`startup-install-validation.json`. Owned probe pod removed. No hardware cluster
was changed; the user must copy the updated chart and upgrade the existing release.

## Discovery completion — controller pending

2026-10-25: implementation and the unified controller harness are prepared.
The worker read all seven originals and verified all seven image SHA-256 hashes
against the private manifest. This focused evidence-integrity check is outside
the controller's uploaded/sanitized fixture boundary. Current official source
was read at `4533a85`; preserved `dragonvm` services were inspected read-only on
explicit context `fhs-test`, with the alignment web/worker/databases Running.

Neither configured controller command was run by the implementation worker.
No syntax, fixture, native API or plugin acceptance pass is claimed for this
change yet. The [controller entrypoint](acceptance_discovery.py) must pass before
completion; a missing prerequisite or native-model failure must remain a failure.
No deployment, publication, controller mutation or physical hardware test was
performed. Existing validation entries above describe earlier changes only.

The continuation narrowed the existing native harness to the supervisor's
focused scope: seven LLDP rows through Nexus tasks, actual SDK task environment,
QSFP metadata/empty ports, exact and explicitly verified DAC endpoints, repeated
breakout observations, existing-cable preservation, partial/failed reads,
idempotence, read-only routes, rack placement and two independent PSU mappings.
It retains representative native invalid/occupied checks and authenticated plugin
assertions; no new framework or asset lifecycle suite was added.
`wiki/task-creation.md` was absent when requested in this worker checkout; the
supervisor correction supplied in the task was read and followed directly.

Continuation evidence checks: all seven original image hashes match the private
manifest; 19 local documentation link targets across the importer, operator
guides, harness README, provenance and fixture README exist. These checks cover
private evidence integrity and documentation, outside controller runtime checks.
The fresh fetch-only official source check confirms `4533a85` remains current.
No configured acceptance command or additional runtime suite was executed.

## Discovery completion — accepted 2026-10-25

Supervisor recovery completed the same task after controller acceptance exposed
two issues: scenario variables lost precedence to shared defaults, and the
metadata filter rejected Ansible-tagged integer rack units. The fixture now uses
operator-equivalent extra-vars; validation accepts integer subclasses but rejects
booleans. The targeted nine-test discovery suite passed after that correction.

The same focused controller entrypoint passed on existing `fhs-test`, retained
release `fhs-inventory-alignment` revision 4, fixture `SYN-DISC-c4f3c69c`:

- Real Ansible routing/discovery fixtures and importer syntax passed.
- 50 report assertions passed: seven LLDP cables, dynamic populated/Removed
  QSFPs, SDK venv/root/user, metadata and Inventory assets, breakout associations,
  exact and explicitly verified endpoint-pair DACs, conflict preservation,
  partial/failed reads and unchanged repeated apply.
- Native rack-unit placement and PSU1/PSU2 cables to distinct PDUs passed,
  including representative invalid/occupied checks and missing-data preservation.
- All nine native network cables appeared in authenticated Topology Views;
  Inventory asset page passed. Inventory 2.7.1 and Topology Views 5.0.0 active.
  PVC bindings and protected credentials were unchanged.

Sanitized report: ignored pipeline `runs/netbox-discovery-completion-20261025/acceptance-final.json`.
Private detailed evidence remains on dragonvm at
`/tmp/fhs-discovery-completion-0gnix1wk/`. No physical device was contacted;
plugin pages use Django Client, not browser visual QA. Prior failed reports and
controller logs remain preserved. No claim of physical hardware discovery.


## Hardware corrections and host isolation — 2026-10-25

Retained delivered chart release/namespace `fhs-inventory-alignment`, explicit
context `fhs-test`; NetBox `4.7.0`, Inventory `2.7.1`. No deployment changes.

- 49 focused tests passed without skips: `test_fru`, `test_importer`,
  `test_routing`, `test_task_flow`; real Ansible syntax check passed.
- `acceptance_fru.py`: 20 native assertions passed, including manufacturer-only
  and model-only corrections, stale bootstrap fallbacks, retained chassis asset
  IDs, repeat-import stability and partial/failed/missing discovery preservation.
- `acceptance.py`: 69 native assertions passed for chassis, components,
  FPGA/NIC/Nexus replacement/removal, retained assets, journals and change logs.
- Host-failure routing fixture confirms another Linux host and Nexus imports
  continue while Ansible returns failure for the affected host.

Private synthetic evidence on dragonvm:
`/tmp/fhs-hardware-correction.O5jEViXt/{acceptance_fru,acceptance}.json`.
Local orchestration log: `/tmp/fhs-hardware-acceptance-final.log`.
An initial broad test transfer omitted legacy chart fixtures; the final focused
checks above used their complete dependencies. Local Python-only FRU checks
explicitly skipped native Ansible; the remote focused run had no skips.

Physical hardware remains unverified. Conflicting serial identity, ambiguous
asset ownership and quarantine still require review for the affected host.


## FRU identity and serial-only creation — 2026-10-25

Retained delivered chart release/namespace `fhs-inventory-alignment`, explicit
context `fhs-test`; NetBox `4.7.0`, Inventory `2.7.1`. Services and pipeline state
inspected first; no deployment changes or physical hardware access.

- 50 focused tests passed without skips: `test_fru`, `test_importer`,
  `test_routing`, `test_task_flow`; real Ansible syntax check passed.
- `acceptance_fru.py`: 21 native assertions passed. A selected FRU Product Serial
  alone creates a device with manufacturer `NA` and model `Unknown`; a repeated
  import is unchanged. Valid but misleading DMI identity is ignored. Explicit
  serial/manufacturer/model overrides beat FRU observations. Partial/failed FRU
  reads preserve existing data and type corrections retain chassis asset IDs.
- `acceptance.py`: 69 native importer lifecycle assertions passed, including
  actual compare tasks consuming normalized identity before a chassis rename.
- The FRU task fixture verifies that no Linux chassis-serial file is read.
  DIMM/NVMe component sources and completeness rules are unchanged.

Final native evidence on dragonvm:
`/tmp/fhs-fru-identity.RhffvA2H/{acceptance_fru,acceptance}.json`.
Local logs: `/tmp/fhs-fru-identity-acceptance-final.log` (focused tests/syntax),
`/tmp/fhs-fru-identity-native-final.log` (native acceptance).
The native fixtures were corrected to remove obsolete fallback cleanup and give
an override host independent hardware identifiers. No acceptance was claimed for
those incomplete attempts. Physical hardware remains unverified.
