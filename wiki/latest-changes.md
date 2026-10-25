# Dashboards and telemetry

This page consolidates the earlier “latest changes” snapshot and its 2026-10-23
demo correction. Source inspection history is in the [source map](sources.md);
completed runs remain in the [log](LOG.md). No services were tested for this
wiki refresh.

## Static demo

The self-contained [Grafana demo](../examples/grafana-static-demo/README.md)
provides six views: rack, mesh, FHS/server, switch, interface and VLAN. Its README
owns launch, scenario editing, screenshots and cleanup commands. Grafana binds
loopback; Prometheus and the exporter remain internal.

All demo readings, rates, optics and peers are synthetic. Its nine racks,
132 FHS, 51 switches, 648 mesh cells and 128 interface slots per switch are
presentation coverage, not discovered inventory. Four `fspu1` servers have no
telemetry; `fspu2-fhs1` has a PSU fault; `vccu1-switch eth1/1/3` and
`fspu3-switch eth1/1/1` represent one failed link.

Rack switch tiles include member faults. Mesh **available capacity (%)** is a
deterministic synthetic value: failed links show zero and missing/unknown data
stays gray. Configured physical line rate and selected-link throughput remain
separate. The old Gbit/s mesh-capacity description was superseded by the
[2026-10-23 correction](LOG.md#2026-10-23).

`scenarios.json` accepts `ok`, `degraded`, `fault`, `unknown`, `notdeployed`.
Each scrape rereads the complete file; invalid input returns HTTP 503 and a valid
replacement recovers without restart. Interface overrides affect both link ends;
physical port/QSFP health remains separate. Follow the demo's atomic-file editing
instructions rather than replacing the whole configuration with a partial example.
Recorded Compose/browser, copied-folder and ZIP acceptance is in the dated log;
it does not establish physical telemetry or current lab health.

## Observed dashboards

The [native dashboard sources](../ops/dashboards/README.md) now live under
`ops/dashboards/`; compressed chart assets stay under `platform/`. Six stable
UIDs include `fhs-infra-server`; `fhs-infra-fhs` is obsolete. The source README
owns generation, import ownership, datasource adaptation and navigation details.

Full display is 24 VCC units × 27 FSP units. The documented emulator scope is
4 VCC / 3 FSP units: 16 FHS, seven switches and 12 mesh links. Unit composition
is recorded in [unit topology](unit-topology.md). Missing observations remain
unknown; interface link health cannot establish chassis, PSU or fan health.

The separate servers-only visual fixture marks 116 nonemulated FHS as **not
observed**. It supplies no physical component readings, rates or capacity.
Observed data wins and stale fixture data stays unknown. Do not copy the demo's
synthetic healthy defaults into this path.

[Dashboard validation](../ops/dashboards/VALIDATION.md) and the historical
[review checkpoint](../ops/dashboards/REVIEW-STATE.md) record accepted fixes and
remaining boundaries. Full rack/mesh/peer navigation, title-rename and fresh
collector/import/browser acceptance for the visual fixture remain open in that
evidence. No broader pass is inferred from the static demo.

## Telemetry evidence

[Original node, FHS and switch captures](../ops/telemetry/README.md) retain their
source bytes and [relocation hashes](../ops/source-boundary/PROVENANCE.json).
They are evidence inputs, not a current hardware-health feed. Record device and
exporter versions, units, expected behavior and sanitization when extending them.
Preserve label relationships without publishing credentials or identifying captures.

A single snapshot cannot validate rates, counter resets or history. Pair raw
captures with short representative time series and explicit missing-data/outage
fixtures before claiming observed-dashboard acceptance. Coverage and physical
representativeness remain to be established.
