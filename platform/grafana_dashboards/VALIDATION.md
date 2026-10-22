# Dashboard validation

2026-10-21, implementation worker on dragonvm (hostname
`dragon-lord-Virtual-Machine`, confirmed by supervisor bridge).

- `python3 -m unittest discover -s platform/grafana_dashboards/tests -v`: five
  passed. Covers deterministic generation, full/small inventory, missing-data
  structure, PSU mapping, both endpoint query inputs, URL encoding and source
  consolidation. These checks do not execute PromQL.
- Existing immutable-reference tests: FHS six passed and switch nine passed via
  `python3 -m unittest discover -s /home/dragon-lord/fhs-pipeline-inputs/dashboard-reference/prototype/monitoring/export-backed-dashboards/tests -p test_fhs_dashboard.py -v`
  and the same command with `-p test_switch_dashboard.py`. These validate references,
  not live implementation behavior.
- `python3 -m py_compile platform/grafana_dashboards/live_validate.py`: passed.
- Promtool fixtures are supplied in `tests/promql.test.json`; Promtool is absent
  on this worker's PATH. Docker socket read access was denied. No fixture pass
  is claimed.
- Supervisor bridge response: `awaiting_emulator_live_data`. The readiness file
  was absent when checked. No imports, browser clicks, screenshots or live query
  results are claimed. The bridge requests scoped supervisor execution.

Remaining: execute Promtool and actual query/browser acceptance, inspect real
screenshots (especially matrix row/column links, panel overflow and full counts),
verify title rename/restoration, then obtain independent intent review. This is
an implementation candidate, not a completed acceptance report. No hardware or
live traffic behavior is proved by these emulated sources.

- Required completion gate:
  `python3 /home/dragon-lord/fhs-pipeline-inputs/check-dashboard-completion.py`
  failed with `Missing supervisor real lab acceptance evidence`.
- `git diff --check` passed for tracked changes. Generated files remain untracked
  for controller/reviewer inspection; no commit or push was made.

2026-10-22, continuation on `dragon-lord-Virtual-Machine`:

- Six implementation tests passed after adding the LLDP opposite-endpoint link;
  generated JSON matches the generator. Fifteen unchanged reference tests passed.
- `python3 -m py_compile platform/grafana_dashboards/live_validate.py` and
  `git diff --check` passed. All 79 recorded input hashes still match.
- Browser acceptance now checks rack-to-switch, both broken-link endpoints,
  destination selectors, jobs, datasource, instance selectors and time range.
  Live queries also check all 51 unit aggregates and the 128 observed FHS,
  51 switch and 1560 LLDP inventory counts. These are pending execution, not passes.
- Submitted exact scoped argv and script hash in ignored
  `.pipeline-bridge/request.json`, outside controller-owned runs. No worker
  import or cluster mutation. Promtool remains absent from PATH.

- Supervisor review requested a browser origin guard and unconditional browser
  cleanup. Added guarded same-origin fetches with redirects disabled, foreign
  request aborts, blocked service workers and `finally` cleanup. Two guard tests
  pass; total implementation suite now eight passed. New bridge request ID:
  `dashboard-issue2-implement-20261022-origin-guard-v3`.
- Readiness now reports `ready_for_grafana_validation: true` and the full
  configured inventory. This is operator readiness, not dashboard acceptance.
- Independently compared all 648 generated VCC-side interface destinations with
  the immutable operator topology: all match.

2026-10-22, bounded ownership continuation:

- Twelve candidate tests passed on dragonvm, including four ownership-search
  checks: unknown UID uses search only, foreign ownership rejects, pagination
  completes, and incomplete bounded discovery fails closed. Fifteen immutable
  reference tests passed. All 79 input hashes still match.
- Import now uses `overwrite=false`; existing owned dashboards retain their
  ID/version for conflict detection. No unknown-UID GET before creation. Search
  parameters follow the [Grafana search API](https://grafana.com/docs/grafana/latest/developer-resources/api-reference/http-api/api-legacy/folder_dashboard_search/).
  Installed API behavior remains subject to supervisor execution.
- Frozen validator dependencies and hashes submitted through ignored
  `.pipeline-bridge/request.json` as
  `dashboard-issue2-implement-20261022-bounded-ownership-v5`. No worker import.
- PromQL fixture generation, Python compilation and `git diff --check` passed.
  Promtool is still absent from PATH; fixture execution remains pending.
- Visually inspected immutable prototype rack, matrix and component screenshots.
  These are reference designs, not screenshots or acceptance of this candidate.

2026-10-22, reduced-scope implementation stage (source only):

- Defaults and checked-in layout now use VCCUnit1..4 / FSPUnit1..3: 16 FHS,
  seven switches and 12 mesh cells. Live assertions require 12 present FHS,
  four FSPUnit1 NoData and 56 LLDP entries. Alarm/link scenarios and UIDs remain.
- `python3 -m unittest discover -s platform/grafana_dashboards/tests -v`:
  16 passed, including default CLI reproducibility, explicit 24/27 full-size
  coverage, reduced layout, browser guard, ownership and read-only diagnostic
  handling of a known UID timeout. Baseline reduced default failure is resolved.
- Immutable reference suites rerun with `-p test_fhs_dashboard.py` (six passed)
  and `-p test_switch_dashboard.py` (nine passed), using the reference test path
  above. These remain reference checks, not current dashboard acceptance.
- All 79 recorded immutable input SHA256 values still match. PromQL fixture
  generator produced valid JSON with nine expression cases. Promtool remains
  unavailable on PATH; no PromQL execution pass is claimed.
- Python compilation passed for generator and live validator. Tracked diff
  whitespace check against `026a40cd2e92b94cf1dd35f2faa4a68c13a361ea` and a
  separate candidate `.py`/`.md`/`.json` whitespace scan passed.
- Added separate existing-rack screenshot and exact-13.2.3 read-only diagnostic
  modes, with 15-second HTTP socket timeout. [Supervisor continuation](SUPERVISOR.md)
  records tagged official API/service sources, bounded operations and emulator
  coordination requirements. The known-UID hang invalidates an unknown-only
  diagnosis; no installed root cause or repair is proved.
- No live calls, imports, screenshot captures, emulator edits, ELK changes,
  controller/run edits, commits or pushes in this stage. Existing screenshot,
  paused-profile persistence, actual reduced queries/navigation/screenshots and
  independent intent review remain supervisor/controller gates.

## Prototype restoration — 2026-10-22

Baseline on dragonvm: 19/19 tests passed before changes. Updated geometry
supersedes old assertions for separate rack panels, the small table matrix
and individually oversized FHS reading panels. Updated contracts cover nine
42U racks, 183 hardware objects (23 deployed / 160 absent), 648 mesh cells,
128 switch slots, compact component grouping, UID links and unavailable config.
Updated suite: 21/21 passed. Browser and ownership guards are retained.

Owned imports/readback passed for all six stable UIDs on Grafana 13.2.3.
268 generated PromQL queries executed against the actual datasource without
errors (empty results allowed). Actual 1440×1000 browser captures are retained
privately at `/tmp/fhs-grafana-exact-live` on dragonvm. Native switch lane 3
click opened the expected interface UID and `eth1/1/3` selection successfully.

Initial visual QA corrected missing Canvas fields, neutral counts, overflow
and blank-label edit text. Query success does not establish hardware health.
Incomplete scrape coverage keeps some deployed FHS components Unknown;
switch optics/hardware and VLAN configuration are unavailable. Independent
review and full rack/mesh/peer click and title-rename checks remain pending.
