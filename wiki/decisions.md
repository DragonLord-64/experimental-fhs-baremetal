# Decisions and open questions

Current implementation and test limits are indexed in the
[environment plan](test-environment-plan.md). Dated entries retain the original
scope decisions; a later decision can supersede an earlier deferral.

## Confirmed with the user — 2026-10-21

- Use a private experimental GitHub repository; publish tested work there and let
  the user transfer accepted changes to official SKA repositories. Never push upstream.
- Use existing hardware first, target zero cloud spend and stay below US$10/month.
  No cloud purchase is authorized.
- Keep short linked notes with evidence. Resource/NetBox ownership is recorded in
  [controller resources](resource-layout.md).
- The Hyper-V VM and detailed Grafana scope were initially plans. Subsequent
  [lab evidence](test-environment-plan.md#recorded-validation) and
  [dashboard work](latest-changes.md) supersede those early deferrals.

## Confirmed with the user — 2026-10-23

- Test the current native NetBox importers with the delivered chart on existing
  dragonvm `fhs-test`. [Lab authority](../AGENTS.md#lab-test-authority) permits the
  required disposable lab/data/resource changes; both host operating systems stay running.
- Spare-parts integration was deferred then resumed on 2026-10-24. The
  [plugin trial](../ops/platform/inventory-trial/README.md) is historical evidence;
  [integrated acceptance](../ops/platform/inventory-alignment/VALIDATION.md) now
  covers asset retention and installed-record replacement.

## Confirmed with the user — 2026-10-24

- Keep one public [NetBox importer](../playbooks/netbox/netbox_import.yml) for
  Linux/FHS and NX-OS, with separate family collection. Never run server discovery
  on a switch. Other network operating systems need their own collector.
- Physical identity follows serial. Assets survive installed-record removal;
  complete explicit discovery scopes may reconcile absence, while partial/failed
  scans preserve records. Parent journals retain replacement history. See
  [reconciliation policy](resource-layout.md#import-decision--2026-10-22).
- Keep manual DAC stock/quarantine available without inventing cable endpoints.
  Assets, native topology and history have separate roles. Change-log retention
  is configured independently of journals and backups.

## Confirmed with the user — 2026-10-24 pipeline cleanup

- Use local task intake/scouting, one implementation worker and user review. The
  CLI manager inspects the queue/lab; no screening, per-task manager or review agent.
- Match checks to changed behavior. The controller runs configured acceptance
  once; defaults are ten minutes per worker, two minutes per check and three
  launches. Scope paths are guidance, not a filesystem boundary. See
  [workflow and commands](../ops/agent-pipeline/README.md).
- Docs/wiki changes use content/link checks. Real chart/importer acceptance is
  for relevant runtime changes, not a requirement to redeploy for every edit.

## Open questions

- Versioned discovery-inventory YAML and round-trip semantics; current direct
  importer behavior is implemented, the general offline boundary is still design work.
- Guest boot/provisioning after the bounded KVM capability check; see
  [Bifrost limits](../ops/provisioning/README.md).
- Representative telemetry/time-series coverage and remaining observed-dashboard
  navigation/fixture acceptance; see [dashboard boundaries](latest-changes.md).
- Broader role container/VM/hardware coverage and CI runner access. Existing
  configured workflows are not evidence of successful CI or physical validation.
