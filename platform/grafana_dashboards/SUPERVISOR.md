# Supervisor continuation

Keep the paused controller, checkpoints and all unrelated work intact.
Do not resume NetBox/Bifrost or logging. Preserve Grafana 13.2.3 and its data.

Supply `GRAFANA_URL`, `GRAFANA_USER` and `GRAFANA_PASSWORD` privately.

```bash
timeout --signal=TERM --kill-after=10 s 600 s /home/dragon-lord/fhs-docs-tools/bin/python \
  platform/grafana_dashboards/live_validate.py --visual-only --import-owned \
  --output /tmp/fhs-grafana-visual
```

This imports six owned UIDs using bounded ownership discovery, foreign-folder
rejection and optimistic version checks. It never changes credentials, a
source dashboard title or an unrelated dashboard. Same-origin cookie browser
requests continue without injected credentials or response buffering.

Inspect all six actual captures and lower rack, FHS PSU, switch hardware/LLDP
and interface LLDP sections. NoData is acceptable; login/loading/error screens
are not rendering success. Current visual acceptance includes the nine 42 U
racks,648 mesh cells and 128 switch interface slots. Parent hardware health,
optic readings and VLAN allowance remain Unknown where no observations exist.

The full query scenario gate retains earlier strict sensor-coverage assertions;
current native scrape filtering prevents claiming all healthy FHS components.
Run meaningful selected queries independently for the visual milestone. `live_validate.py --browser` implements rack/FHS, rack/switch, mesh/switch,
lane/interface and peer/opposite-endpoint clicks, return paths and context
assertions. It captures all six views, both faulted switches and fspu1/fspu2.
After source gates, supervised import/readback and scenario/query acceptance,
run navigation separately against the already imported owned dashboards:

```bash
/home/dragon-lord/fhs-docs-tools/bin/python platform/grafana_dashboards/live_validate.py \
  --navigation-only --output /tmp/fhs-grafana-navigation
```

This mode performs no imports and does not claim scenario/query acceptance.
Inspect the captures; implementation is not live
acceptance evidence. Title-rename acceptance remains separate.


## Refinement acceptance (pending)

After independent source review and configured checks, generate query inputs:

```bash
python3 platform/grafana_dashboards/promql_tests.py > /tmp/fhs-promql.test.json
promtool test rules /tmp/fhs-promql.test.json
python3 platform/grafana_dashboards/evidence_plan.py > /tmp/fhs-components.json
```

Resolve `$job`, `$node_job`, `$instance`, `$node_instance` from actual datasource
selections. Execute every `status_query` and `reading_queries` through the
Prometheus instant-query API at one recorded evaluation time. Retain sanitized
results as supervisor artifacts. Report all 336 selections by state and missing
primary readings; do not replace missing readings with healthy values. Confirm
84 fspu1 selections are unknown, and distinguish unsupported coverage from the
PSU1 fault / overall degraded scenario on fspu2-fhs1. The catalog is 21 per
host; 168 is not the full 16-host scope.

Use the guarded import command above only after those source gates. Read back
all six owned UIDs. Click rack → FHS, rack → switch, mesh selection → switch,
switch lane → interface and LLDP peer → opposite interface; check datasource,
time and selection values. Inspect all six fresh screenshots, lower rack rows,
compact component rows and port slots. Mesh cells retain `ND` / `?`; verify
the visible key explains `not deployed` / `unknown` and those symbols fit.
Confirm dynamic headers show canonical selector display text, compound table
identities show e.g. `fspu1-fhs1`, and mesh → switch links preserve native
query values, datasource and time after actual browser interpolation. Verify one down lane leaves shared
optics independent and deployed parent unknown without hardware telemetry. Select
`fspu4-switch` and confirm all parent ports show `not deployed`; select
`vccu1-switch` and confirm parent ports remain `unknown` despite the down lane. Throughput
is separate RX/TX at the selected vccu endpoint, converted from observed
5m octet rates to Gbit/s. Confirm about 0.000008136 Gbit/s per direction on
vccu1/fspu1 where the supplied probe measured 1016.9491525423729 bytes/s;
current values may differ. Confirm available rates survive down-link state,
and missing rates stay unknown. Capacity/utilization remain unknown; no capacity
is inferred from host speed metadata. Record unsupported optics/fans/VLANs.

Publication remains gated by actual live acceptance. Trusted publisher uses a
normal fast-forward to private `development` only; do not create or push main.
No worker imports, commits or pushes.

## Visual fixture (supervisor only)

Source-only candidate; no live validation claimed. Read-only inspection of
`~/fhs-emulators-work/ops/emulators/render.py` found ConfigMap
`fhs-emulators/monitoring-fixtures`, directory-mounted at `/fixtures` in the
existing `node` container with `--collector.textfile.directory=/fixtures`.
`integration.py` defines `node-emulator` with a 15s scrape and no metric keep
filter. Recheck that runtime contract before applying; do not edit that checkout.

After independent review, supervisor explicitly selects disposable context
`fhs-test` and verifies the running pod uses this ConfigMap as a directory
(no subPath/items restriction), and the actual scrape has no filter dropping
`fhs_visual_status`. Capture a private ConfigMap snapshot, then render a patch:

```bash
kubectl --context=fhs-test -n fhs-emulators get configmap monitoring-fixtures -o json > /tmp/fhs-fixture-before.json
python3 platform/grafana_dashboards/visual_fixture.py --configmap-snapshot /tmp/fhs-fixture-before.json --output /tmp/fhs-visual-patch.json
kubectl --context=fhs-test -n fhs-emulators patch configmap monitoring-fixtures --type=json --patch-file=/tmp/fhs-visual-patch.json
```

Review the patch before the last command. It tests UID/resourceVersion and adds
only `data["visual-status.prom"]`; `node.prom`, other keys and pod configuration
are untouched. A conflict requires a fresh snapshot and review. No rollout or
new workers. Wait for projected volume refresh and two scrapes (bounded to five
minutes). Read back the ConfigMap and compare all original keys byte-for-byte;
only the separate visual key may differ. Check collector scrape errors remain
zero and exactly 116 fixture samples reach Prometheus. Rollback removes only
that key with a fresh UID/resourceVersion guarded JSON Patch; never restore the
whole snapshot over intervening edits.

Through a supervisor-verified tunnel to this lab Prometheus:

```bash
python3 platform/grafana_dashboards/validate_visual_fixture.py --namespace fhs-test --prometheus-url http://127.0.0.1:9090 --job fhs-emulator
```

This read-only hook checks exact feed identities/count/values and 132 status
queries plus 16 observed-only comparisons. Only visual hosts require green;
actual hosts must preserve observed-only status, including unknown from incomplete
coverage. Missing fspu1 and degraded fspu2-fhs1 remain explicit scenario gates.
Its namespace argument is an acknowledgement, not URL attestation.
Retain sanitized results at a recorded evaluation time. Separately verify PSU1
fault, missing fspu1 readings, unchanged actual sensor samples/`up`, seven switch
and twelve link scenarios, and absent fixture readings. Execute generated
Promtool tests before import. Use the existing six-owned-view import/readback
and navigation procedures; inspect all six screenshots, fixture rack labels,
fspu4 detail unknown readings, fspu1 unknown, fspu2-fhs1 degraded, unchanged mesh
ND and native peer role/number navigation. No worker performs these operations.

Trusted publication freezes the reviewed diff, untracked source files and
SHA256/check evidence before live acceptance. Recheck the frozen content before
normal fast-forward push to private `development` only. Immutable baseline
`baselines/grafana-20261022` at `12c2063a532f246611aa55c74595efe069a8b90f`
must remain unchanged; verify remotely as supervisor. Never publish to main.
