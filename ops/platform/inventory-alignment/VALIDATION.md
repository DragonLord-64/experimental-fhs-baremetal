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
