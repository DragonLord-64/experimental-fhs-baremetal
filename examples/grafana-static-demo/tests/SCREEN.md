# Screen — 2026-10-22

Start: `05fdae2134a2023467a1cb5af5a657f7eb3daa71` (also HEAD).
Initial working tree and diff against start were empty; no partial demo folder
was present. `refs/heads/baselines/grafana-20261022` was absent locally;
no refs were changed and remote baseline state was not checked.

## Source and baseline

- `platform/grafana_dashboards/generated/{rack,mesh,fhs,switch,interface,vlan}.json`:
  six accepted native layouts, stable UIDs and navigation. Copy into the demo;
  preserve geometry and links. `native-layouts.json` freezes panel/Canvas geometry,
  titles, links and destination selector values from start, not query expressions.
- `platform/grafana_dashboards/{generate,exact}.py`: native query helpers,
  inventory, selectors, 9×42U placement, 24×27 mesh and 128 interface slots.
- `platform/grafana_dashboards/{components,deployed-interfaces,visual-inventory}.json`:
  component reading catalog, lab endpoint identities, 116-server visual partition.
  Runtime must use only files inside the delivered folder.
- `platform/grafana_dashboards/README.md`: identity/provenance contract and
  missing numeric readings; `tests/test_refinements.py` covers independent
  parent/optic health and native directional rates. Existing source vocabulary
  includes `not deployed`; the requested demo spelling is `notdeployed`.

Baseline command (before adding tests):

```bash
python3 -m unittest discover -s platform/grafana_dashboards/tests -v
```

47 tests passed in 8.119s. These are offline source checks, not actual PromQL,
Compose or browser acceptance. No containers or external services were run.

New standalone entry point:

```bash
python3 examples/grafana-static-demo/tests/test_unit.py
```

Initial red result: 3 methods, 6 failures (four missing launch inputs,
executable launch check, six absent dashboards), one method passed (symlink
containment). It deliberately exposes the absent deliverable. Extend this entry
point with actual exporter HTTP/schema/hotread and enum/metric contracts once
an exporter interface exists; these initial tests alone cannot establish acceptance.

## Implementation acceptance

Deliver one portable folder and ZIP, with three pinned services (Grafana 13.2.3,
Prometheus 3.15.0, explicit compatible Python image), bounded workers and roughly
768/256/64 MiB limits. Relative mounts only, Grafana on configurable loopback
13000, other services internal. No repo/host Python dependencies, Docker socket,
privileged devices, host networking, cluster work, host power operations, commits
or pushes. Only this demo folder may change. Keep other services/resources intact.

JSON edits use simple `ok/degraded/fault/unknown/notdeployed` enums for servers,
components, links, physical ports and transceivers. Read/validate every metrics
request; invalid input must return HTTP error and recover on correction, never
silently reuse stale data. Document atomic replacement; mount the containing
directory so replacement remains visible. No fabricated sensor values for colors.
Explicit demo status metrics/adapters may augment native queries without changing
layouts/navigation. Preserve native raw identity labels and lowercase visible names.

Keep original task's exact default scenarios: 16 replay hosts (4 vccu/3 fspu),
fspu1 four FHS unknown, fspu2-fhs1 PSU1 fault/overall degraded, other configured
replay components healthy; 116 other servers overall ok by explicit assumption,
components/readings unknown. One down logical link vccu1 port1/interface3 to
fspu3 port1/interface1 derives both ends and mesh. Physical port/QSFP status
independent and unknown unless configured. Nonreplay switches/mesh remain NoData
while full potential inventory remains displayed. Optional numeric readings/rates
must preserve native units/labels and explicit synthetic provenance if supplied.

Add real HTTP tests (valid, malformed, invalid schema/value, hotread, recovery),
all enum mappings and scenario queries, both link ends/mesh, independent port/QSFP,
and missing-number behavior. Supervisor must execute bounded owned Compose
config/build/up, Grafana API/query checks and screenshots for all six dashboards,
FHS fault/mesh down/independent port, edit fault→ok→back without restart/rebuild,
invalid/recovery, launch rerun, occupied-port isolation, copied-out folder and ZIP
extraction launch. Clean only owned projects; keep artifacts outside deliverable.

Do not run Docker in the worker. Implementation submits ignored bridge request
with unique operation, exact bounded runner argv/hash, owned names/labels/ports/
limits/artifacts/cleanup. New executable edits require renewed review. Await matching
supervisor response up to 30 minutes with short polls. Actual acceptance requires
matching response plus supervisor acceptance and exact reviewed source hashes;
never substitute offline tests or screenshots of references. Controller additionally
runs supervisor-owned `.pipeline-bridge/check-acceptance.py`. Root supervisor alone
handles later private-origin publication. Preserve all original task constraints.
