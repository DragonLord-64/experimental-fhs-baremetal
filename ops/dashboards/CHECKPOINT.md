# Grafana checkpoint — 2026-10-22

Requested private checkpoint of the current six-dashboard candidate and scoped
Grafana resource overlay. This branch is not accepted for development integration.
No secrets, browser sessions, raw captures or Python caches are included.

Evidence: baseline19/19 tests, updated21/21 tests,268 executed panel queries,
six owned imports/readbacks on Grafana13.2.3, native switch-to-interface click.
Actual screenshots remain private runtime artifacts on dragonvm.

Open review P2: absent inventory and deployed missing telemetry currently
converge to Unknown in FHS, interface and selected-mesh drilldowns. Repair must
retain NOT DEPLOYED versus TELEMETRY MISSING as separate states. Full rack,
mesh and opposite-peer clicks and title-rename acceptance are also outstanding.
Some native FHS fields are dropped by scrape filtering; unsupported switch
optics/hardware and VLAN config remain unavailable. No healthy data is invented.
