# Logging validation

2026-10-22 UTC, implementation checkout based on `09a715c`.

- `python3 -m unittest discover -s ops/platform/logging -p 'test_*.py' -v`: six tests passed. Covers finite append/exclusive creation, run validation, exact field/count checks and corruption rejection, priority processor correspondence with the existing role, scoped bootstrap API requests without document injection, and rejection of overprivileged existing publisher roles.
- `python3 -m py_compile ops/platform/logging/*.py`: passed.
- Canonical read-only source `/home/dragon-lord/fhs-pipeline-inputs/dashboard-contract/topology.py` identifies VCCUnit1/FHS1 as `vccunit1-fhs1`. No topology or other telemetry producer changed.
- `bash -n ops/platform/{monitoring-test,monitoring-deploy,deploy}.sh`, Filebeat playbook Ansible syntax check, and local chart Helm lint passed (optional chart icon recommendation only).
- Supervisor probe `logging-one-server-probe-20261022` returned 0: systemd 259, no Filebeat or journal-remote executable in PATH, no standalone kubectl. Reported Docker memory `fhs-test 5.404GiB / 5.141GiB`; unrelated `filebeat`, `elasticsearch`, `kibana` and `dotworld-otel-lgtm` containers were present and preserved. No journal contents were read. The first probe could not inspect Kubernetes because `kubectl` was absent; follow-up `logging-one-server-prerequisites-20261022` uses the existing minikube wrapper.
- Queued supervisor probe `logging-one-server-probe-20261022` through the ignored bridge. No live action was performed by this worker.

Supervisor prerequisite check `logging-one-server-prerequisites-20261022` returned 0:
Elasticsearch API version is 9.5.5; publisher password Secret exists; no supported
journal-remote executable was found in the checked system directories. Role and
index-template lookups returned HTTP errors (status not recorded by this probe);
no Filebeat ILM policies were returned. No Elasticsearch changes were made.
Supervisor operation `logging-one-server-bootstrap-ingest-20261022` returned 0.
The reviewed command ran in a transient user scope capped at 256 MiB / 1 CPU.
Scoped bootstrap passed without injecting documents. Actual Filebeat 9.5.5 ingested
`logging-20261022-1` and `logging-20261022-2`: six exact events each, canonical host
only, priorities/levels, raw messages, service/process, IDs and source timestamps
verified against Elasticsearch search results. Each source was 2266 bytes. Both
runs passed clean registry restart/no replay, appended-event delivery and invalid
publisher HTTP-401 rejection. The launcher stopped owned publishers/forwarding,
removed private credential files and completed the separate-source reapply.

This is **explicit filestream fallback evidence**, not journald or Ansible role
coverage. The exact installed-tool limitation is above. Clean restart demonstrates
registry retention, not crash safety or exactly-once delivery. The native
`filebeat_writer` publisher is fixed in config; bootstrap creates a missing role
only within the owned index pattern and rejects overprivileged existing grants.
Administrative credentials were used for bootstrap/search, never Filebeat publishing.

Sanitized temporary evidence: `.pipeline-bridge/ingest.log`,
`/tmp/fhs-logging-check-{1,2}/{result,first-search,final-search}.json`.
Discover operation `logging-one-server-discover-20261022` returned 0. The supervisor
ran the actual browser outside Kubernetes in a 768 MiB / 1 CPU transient user scope.
It created/reused data view `fhs-one-server-logs`, targeting only
`filebeat-fhs-one-9.5.5`, time field `@timestamp`. The actual screenshot
`/tmp/fhs-logging-discover/discover.png` shows six rows for `logging-20261022-2`,
filtered by run and `host.name: "vccunit1-fhs1"`. This implementation worker
visually inspected host, info/warning/error, event IDs, service, messages and UTC
browser timestamps; no credentials are visible. `.pipeline-bridge/discover.log`
records capture, and `.pipeline-bridge/response.json` and
`.pipeline-bridge/supervisor-acceptance.json` record supervisor inspection and
owned cleanup. The browser's `result.json` retains its pre-inspection
`screenshot_inspected: false`; the separate supervisor record supplies inspection.
The supervisor reports private credential JSON removed and no owned Filebeat
processes left. Existing Grafana screenshot/dashboard scope is unchanged.

Resource evidence is limited to the preflight Docker measurement above and reviewed
scope limits; no post-run VM memory measurement is present. No persistent producer
was left running. Kibana is pinned to 9.5.5 in the lab values; actual Discover worked,
but a Kibana API version response was not recorded. Do not infer either measurement
from successful ingest. Offline constructed search fixtures are verifier unit tests,
not evidence of Elasticsearch ingestion.

The earlier stage-end gate ran before the asynchronous Discover response and failed.
After completed proof, `python3 /home/dragon-lord/fhs-pipeline-inputs/check-logging-completion.py`
passed in this implementation stage. This gate reads supervisor acceptance; it does
not replace independent review of the whole goal. The controller owns that fresh
review, including source provenance, privileges, screenshot and resource limitations.
No live ingest was repeated during this documentation reconciliation.

Implementation reconciliation checks: six unit tests, compilation of all logging
Python scripts, shell syntax checks above and `git diff --check` passed. Re-running
`fixture.verify` against each saved final Elasticsearch search response and its
original NDJSON source passed: six exact events for each of the two run IDs.
No test was weakened and no live operation was repeated.
