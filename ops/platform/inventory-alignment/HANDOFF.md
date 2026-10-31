# NetBox Inventory alignment — screen and baseline

2026-10-24. Screen only; production code unchanged. Worktree:
`/home/dragonlord/.codex/worktrees/netbox-inventory-alignment/experimental-fhs-baremetal`,
initial `origin/development` `eee2d6d`. Preserve the dirty primary checkout.
Read [root instructions](../../../AGENTS.md), [workflow](../../AGENTS.md),
[platform](../README.md), [umbrella checks](../umbrella/README.md), and
[trial](../inventory-trial/README.md). No nearer AGENTS files were found.

## Task and acceptance

Align the FHS repository, tested NetBox Inventory trial, MAIN deployment and
importer. Integrate MIT `netbox-inventory==2.7.1` with NetBox `4.7.0` into the
portable `platform/charts/fhs-platform` deployment and legacy `platform/` +
`ops/platform` lab entrypoints. Enable `sync_hardware_serial_asset_tag: true` and
`Faulty / quarantine` (`faulty`, red). Prove actual lab activation and importer
behavior; config/render checks alone do not complete this task.

- Create/reconcile physical assets without losing stable serial identity or
  retained history on repeat import, removal or replacement. Chassis serial is
  physical identity, not hostname. Missing/ambiguous serials cannot justify
  invented identities or destructive reconciliation.
- Replace installed module records by delete/recreate when physical serial
  changes. Retain the old asset and log old/new serial, bay and result in a
  journal attached to the parent device. Surviving assets differ from installed
  module records. Return removed assets to stored; do not infer faulty status
  from absence alone.
- Reconcile absence only for explicitly scoped, successful complete sections.
  Failed, partial or unselected scans preserve existing inventory. A successful
  empty section differs from a failed or missing section.
- Do not invent cable peers. Standalone DAC assets do not require native Cable
  links. The standard YAML discovery/import boundary is a recorded design,
  not an implemented requirement in this baseline; implement a coherent scope
  and document remaining boundary work honestly.
- Parent handles safe checkout synchronization and upstream source review.
  Official branch `development2` is `0658e93b7fa0ebbcdbcb85afcce99b1cbbc45bcd`;
  preserve its relevant fleet MAC exclusions (`ee:ee:ee:ee:ee:ee`,
  `00:00:00:00`) and README deployment profile (release `mid-cbf-hw`, namespace
  `hw-management`, prefix `/mid-cbf-hw`). Most recent source changes are already
  represented. Retain launcher static-route fixes and RWO affinity behavior.
- Only private origin may receive pushes. No production hardware access. Never
  stop either host OS. Parent owns remote inspection/mutations; coordinate lab
  work and always name Kubernetes context `fhs-test` (default is `monitoring`).

## Source findings

- [FPGA/NIC synchronizer](../../../playbooks/netbox/library/fhs_fpga_sync.py)
  returns immediately on empty cards, finds installed records by device+bay,
  then PATCHes serial in place. It creates no plugin assets or journal entries.
  NIC telemetry merge and FPGA interface adoption must survive the change.
- [Shared client](../../../playbooks/netbox/module_utils/fhs_netbox.py) only
  finds/ensures single objects. Lists need pagination; deletion must handle real
  HTTP 204 (the current generic request always calls `response.json()`). Cache
  invalidation matters after deleting/replacing a bay occupant.
- [Server apply](../../../playbooks/netbox/tasks/apply.yml) creates devices by
  hostname without chassis serial, components by device+name, and invokes both
  module kinds without completion metadata. Discovery failures are mostly
  tolerated and empty desired lists initialized by
  [system tasks](../../../playbooks/netbox/tasks/system.yml). Do not infer
  complete discovery merely from reaching the apply task.
- [Nexus apply](../../../playbooks/netbox/netbox_import_nexus.yml) also updates
  modules by device+bay and serial. Its
  [normalizer](../../../playbooks/netbox/filter_plugins/nexus_inventory.py)
  records omissions and local DAC ends but does not discover cable peers.
- [Canonical values](https://github.com/DragonLord-64/experimental-fhs-baremetal/blob/466522bf2dff260ab8f76c1a9c999331233125b1/platform/netbox.yaml) and
  [umbrella values](../../../platform/charts/fhs-platform/values.yaml) load no
  plugins. The [lab overlay](https://github.com/DragonLord-64/experimental-fhs-baremetal/blob/466522bf2dff260ab8f76c1a9c999331233125b1/ops/platform/dragonvm/netbox.yaml) pins the base image, so
  changing only a parent image setting can leave the lab using an unextended
  image. Web, worker and housekeeping must all use the plugin-bearing image.
- [Trial Dockerfile](../inventory-trial/Dockerfile) installs the pinned plugin
  and collects static files. [Trial acceptance](../inventory-trial/acceptance.py)
  tests asset assignment, serial/tag sync, retained asset after module deletion,
  stored/used/faulty history and manual standalone DAC quarantine. It does not
  prove the delivered chart or either importer. Update stale deferred-scope
  statements in wiki/trial docs after integration is actually tested.
- Verified directly from the public PyPI `netbox-inventory` 2.7.1 wheel:
  `signals.prevent_update_serial_asset_tag` REJECTS hardware serial/tag changes
  when an asset is assigned and sync is enabled; it does not mutate the asset.
  `free_assigned_asset` snapshots the asset, clears assignment, sets stored and
  saves with `clear_old_hw=False`. Asset type must match installed hardware;
  serial uniqueness is scoped by hardware type. Asset-to-hardware sync is in
  `models/assets.py:update_hardware_used`. Preserve this ordering constraint.

## Tests and baseline

Run from repository root (same commands can be used in CI):

```sh
python3 -m unittest discover -s ops/platform/inventory-alignment -p 'test_*.py' -v
python3 -m unittest discover -s ops/platform/umbrella -p 'test_*.py' -v
```

Python 3 has requests, PyYAML and Jinja2; Ansible is absent locally. Importer unit
tests stub only the Ansible CLI import and exercise the real synchronizer and
shared HTTP client with a stateful fake. No sockets, credentials or hardware.

Before implementation: existing umbrella **10/10 pass** with loopback permission.
The restricted run had 9 passes and one socket-denied error; escalated rerun
passed the local mock API test too. New alignment suite: **12 cases, 5 pass;
7 failed assertions/subtests and 2 errors**. Failures show no effective plugin
in three rendered paths, no asset creation, no complete-empty removal, missing
MAC sentinel exclusions; replacement errors reproduce plugin rejection of
serial PATCH. Preserved checks cover repeat idempotence, preview with no writes,
partial/missing scan preservation, valid MACs and rejection of real duplicates.

`test_deployment.py` renders actual bundled charts and reads effective NetBox
settings. `test_mac_guard.py` evaluates the task's actual fleet filtering and
assertion using Jinja, with Ansible-compatible extract/flatten/unique filters.
`test_importer.py` models the verified serial-change protection/deletion signals,
not full NetBox validation. `complete=True` is a proposed local module argument
for an explicit successful scope; implementation may rename it consistently
with the task wiring/tests. Tests do not establish CLI wiring, pagination,
transaction rollback, component cascade behavior or real change-log durability.
Add focused regressions when implementing those areas; do not weaken assertions.

## Required isolated service acceptance

Use the delivered umbrella on existing dragonvm `fhs-test`, not another cluster
or a successful standalone trial as a substitute. Inspect current services and
pipeline state first. User authorizes fixing disposable lab resource problems.

1. Build/load the same pinned plugin image used by all NetBox processes; install
   the delivered chart, verify migrations/readiness, `/api/status/` NetBox/plugin
   versions, asset OPTIONS faulty choice and effective runtime sync configuration.
   Recheck main URL/static paths and media consumer affinity.
2. Run current native importer(s) against synthetic fixtures on that service.
   Verify first/repeat asset IDs, real chassis serial handling, FPGA/NIC plus
   inventory-item/Nexus paths actually claimed by the implementation. Test
   replacement, explicit complete-empty removal and failed/partial preservation.
3. Read old asset by original serial/ID, new installed module ID, journal text
   and real NetBox change-log rows after replacement/removal. Check retained
   interfaces/cabling behavior rather than assuming deletion preserves them.
4. Exercise standalone DAC stored/used/faulty transitions with no fabricated
   remote endpoint. Record history retention policy/limits and sanitized results.
   Keep credentials and raw private captures out of Git.

## Addendum — one public importer

New explicit user requirement: combine `netbox_import.yml` and
`netbox_import_nexus.yml` behind user-facing `netbox_import.yml`. Route Linux FHS
and Cisco NX-OS correctly; never run Linux discovery on Nexus. Preserve mixed
inventory, `--limit`, protected credential override, facts/compare/apply/check
modes and retries. Internal family task files are acceptable; any old Nexus
compatibility wrapper must delegate without duplicate device logic.

Agreed boundaries: `tasks/import_linux.yml` and `tasks/import_nexus.yml`.
Group `nexus`, `ansible_network_os: cisco.nxos.nxos` (also `nxos`) and existing
NetBox role groups `device_roles_nexus-switch` / `device_roles_nexus_switch`
identify Nexus. Keep any Linux fleet guard scoped to Linux hosts: a mixed play's
`ansible_play_hosts` otherwise includes switches without Linux discovery facts.
Implementation proposes a local classification/group_by play followed by
separate family plays. Preserve Nexus `network_cli` discovery and delegated local
NetBox writes. A legacy wrapper may request Nexus-only scope.

Added [routing regression](test_routing.py) executes actual play routing with
real Ansible, a four-host synthetic inventory and a private synthetic credential
file. It replaces only internal device payloads with local probes, removes
irrelevant NetBox module defaults, and uses a local `network_cli` transport shim.
Assertions inspect selected family, effective task connection, credential
loading, default retries, mixed inventories, family limits and dispatch under
facts/compare/apply/check. Duplicate family execution on one host is rejected.
This does not validate actual device task bodies, child mutation tag semantics,
network handshakes or real importer outputs; run syntax/list-hosts/list-tasks
against the real entrypoint with installed collections and retain live tests.

```sh
# Real core installed temporarily under /tmp (2.19.3); no repository dependency change.
PYTHONPATH=/tmp/fhs-routing-ansible-runtime python3 -m unittest discover \
  -s ops/platform/inventory-alignment -p 'test_routing.py' -v
```

Before entrypoint refactor: five methods, Linux-only limit passes; eight failed
assertions/subtests establish mixed/Nexus/tag/check misrouting and duplicated
legacy logic. A temporary positive-control router passed mixed dispatch and
effective `network_cli`, establishing the harness can pass a correct router.
Without Ansible installed, the routing class explicitly skips instead of
pretending to test routing. No service or hardware was contacted.
