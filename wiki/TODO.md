# Documentation backlog

Keep documentation work here; use GitHub issues for actionable implementation
scope and acceptance. Runtime gaps are maintained in the
[environment plan](test-environment-plan.md#remaining-work), not duplicated as
completed documentation tasks.

## Recorded milestones

- [x] One concise README per role, referenced by the existing
  [Sphinx structure](../docs/src/index.rst).
- [x] NetBox identity, asset reconciliation, import/export and separate discovery
  families in the [development guide](../docs/src/playbooks/development.md) and
  [importer README](../playbooks/netbox/README.md).
- [x] Current portable platform commands in the
  [canonical chart README](../platform/charts/fhs-platform/README.md), with lab
  procedures kept in [operations](../ops/platform/README.md).
- [x] Switch POAP, Nexus configuration and Bifrost DHCP workflow documented in
  the development guide and [source directory](../playbooks/switch-poap/).
- [x] Historical strict Sphinx builds and representative diagram/page inspection
  recorded in the [log](LOG.md#2026-10-22). Those results apply to their tested revisions.
- [x] Consolidate the stale handoff and dashboard snapshot into current linked
  wiki topics; preserve source inspection history and original local handoff.

## Remaining documentation

- [ ] Complete the observed Grafana operator guide: datasource/job adaptation,
  provisioning/import ownership, missing-data meaning and normal navigation.
  Start with [dashboard sources](../ops/dashboards/README.md); keep
  [synthetic demo instructions](../examples/grafana-static-demo/README.md) separate.
- [ ] Document the versioned discovery-inventory YAML contract when implemented;
  the [current proposal](resource-layout.md#discovery-inventory-boundary--proposed)
  must not be presented as existing offline import support.
- [ ] Record capture sanitization and representative time-series coverage as
  evidence becomes available; see [telemetry requirements](latest-changes.md#telemetry-evidence).

## Pipeline proposals — not approved for implementation

The current [pipeline](../ops/agent-pipeline/README.md) keeps intake, scouting,
manual dispatch, one implementation worker, configured checks and user review.
These ideas are proposals only, not existing behavior or authorization to build:

- Shared test-hardware reservations across tasks/checkouts to avoid concurrent
  use, potentially with a brief health check before tests.
- A maintenance agent that activates when pipeline work gets stuck.

Match nearby repository voice: short descriptions, actual tags, normal commands
and explicit limits. Keep completed results in the append-only log and current
behavior beside source, rather than maintaining competing setup instructions.
