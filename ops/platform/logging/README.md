# One-server logging fixture

Bounded synthetic system/service events for `vccunit1-fhs1` (VCCUnit1/FHS1).
The canonical telemetry topology uses this name. NetBox's device display name
is `lab-nb-vccunit1-fhs1`; its `canonical_name` custom field retains the telemetry
name. All other emulator identities remain metric-only. No application emulation.

The [existing role](../../../roles/filebeat/templates/filebeat.yml.j2) reads journald,
adds `log.level` from `log.syslog.priority`, and publishes directly to Elasticsearch.
There is no Logstash dependency. The role and lab chart pin/default to 9.5.5;
Filebeat and Elasticsearch 9.5.5 were verified live; Kibana is pinned to 9.5.5
but its API version was not recorded. This directory does not change the role.

## Offline checks

```sh
python3 -m unittest discover -s ops/platform/logging -p 'test_*.py' -v
python3 ops/platform/logging/fixture.py generate --directory /tmp/fhs-log-example --run example-001
python3 ops/platform/logging/fixture.py generate --directory /tmp/fhs-log-example --run example-001 --batch 1
```

Each directory accepts one run, three initial events and one append of three events;
repeat creation/append fails. No background generator, rotation or continuous rate.
Six records occupy less than 8 KiB in the test. Each invocation uses current UTC
millisecond timestamps; messages and severity order are deterministic. The contract
preserves `event.original`, `message`, numeric syslog priority, service/process fields,
`event.id`, `labels.test_run` and canonical `host.name`. IDs are `<run>-0` through
`<run>-5`. Only priorities 6/info, 4/warning and 3/error are generated.

## Reviewed VM execution

All live work is queued through `.pipeline-bridge/request.json` outside controller
runs; the supervisor serializes it with emulator/NetBox operations. Do not start
containers, forwarding or deployments from a worker. Reuse the persistent lab
Elasticsearch/Kibana only when explicitly authorized. Logging is currently paused at zero replicas; retain its PVCs and do not run these commands as integration checks. The earlier validation preserved unrelated host containers; those host Filebeat/ELK containers were subsequently removed at user request without deleting volumes.

For future journald coverage, first test isolated journal creation with supported
tools and pinned Filebeat's journald input under separately authorized scope. Never read/copy the host journal, mount it into a container, start
host systemd or use a privileged container. **The supervisor preflight found no `systemd-journal-remote` in PATH,
`/usr/lib/systemd` or `/lib/systemd`, and no Filebeat in PATH. An isolated journal
cannot currently be imported with the installed supported tool; no packages or
privileged workaround were installed. The completed live operation explicitly used
filestream. Journal creation/ingest remains untested.** `filebeat.yml` is a separate explicit filestream overlay for use only
when the supervisor records the exact journal-fixture limitation. It checks the
same priority processor and output/field contract; it does not test journald,
installation, the Ansible role, or journal cursor recovery.

Before running the fallback, the supervisor must verify actual 9.5.5 versions,
existing `filebeat_writer` credentials and permissions, and scoped bootstrap.
The chart's lab values disable writer bootstrap. The writer role allows
`monitor/read_ilm/read_pipeline` and `auto_configure/create_doc` on `filebeat-*`;
never broaden that role or publish with `elastic`. This overlay disables runtime
setup and ILM discovery. Preload a template matching **only**
`filebeat-fhs-one-9.5.5`, with Filebeat-compatible mappings (including date
`@timestamp`, keyword `labels.test_run`, `event.id`, `host.name`, `log.level`) and
an owned bounded-retention ILM policy/write destination. Prefer reuse of verified
existing Filebeat bootstrap where compatible. Bootstrap is a separate reviewed
administrative operation, never a publisher capability. [bootstrap.py](bootstrap.py)
creates only the owned ILM/template/write alias and missing native publisher
user/role from existing private lab credentials. Existing publisher grants are
checked and preserved; a missing role is narrower than the chart (`filebeat-fhs-one-9.5.5*`).
The policy rolls over at 50 MB or one day and deletes at two days. Supervisor bootstrap and two real Filebeat runs passed; see [validation](validation.md).

The reviewed [supervisor-run.py](supervisor-run.py) downloads the official
9.5.5 archive, verifies its official SHA-512 checksum, extracts it under
`/tmp/fhs-logging-tools`, performs scoped bootstrap, and runs validation twice
with separate sources/registries/run IDs. It deletes temporary credential files
and stops its owned port-forward. No host package is installed.

Supervisor command after preparation, using an isolated extracted Filebeat binary:

```sh
python3 ops/platform/logging/validate.py \
  --filebeat /tmp/fhs-logging-tools/filebeat-9.5.5-linux-x86_64/filebeat \
  --credentials /tmp/fhs-logging-private/credentials.json \
  --work /tmp/fhs-logging-check-001 --run logging-check-001
```

The private mode-0600 JSON contains `elasticsearch_url` (bare loopback HTTP forwarding
URL), `filebeat_password`, `reader_username`, `reader_password`. The publisher
username is fixed to `filebeat_writer`. The independent reader needs search access;
its credentials are never passed to Filebeat. No credentials go in command arguments,
Git, evidence or screenshots. The runner only POSTs search requests, never events.

The runner checks the actual binary version, config, invalid publisher HTTP 401,
three exact events, a clean stop/restart with the same registry and no replay after
12 seconds, then three new events. It saves synthetic search results and a sanitized
summary in its private owned work directory. ES refresh/delivery waits are bounded
at 90 seconds per batch. Clean shutdown waits at most 20 seconds. Run under reviewed
supervisor limits of 1 CPU, 256 MiB and 360 seconds; check VM/cgroup memory while the
fullscale emulator is active before starting. No extra ELK stack is needed.

Delivery remains at least once. A clean registry restart is narrower than crash
recovery. `event.id` is an assertion field, not Elasticsearch `_id` deduplication;
crashes or deleting the registry can duplicate records. Keep the source and registry
paired. The finite source bounds storage; do not leave a persistent producer running.

## Discover and cleanup

The separate reviewed [discover.py](discover.py), run with
`/home/dragon-lord/fhs-docs-tools/bin/python`, creates/reuses the owned view and
captures an actual Chromium page outside Kubernetes. Supervisor must create/reuse owned data view `fhs-one-server-logs` targeting exactly
`filebeat-fhs-one-9.5.5`, time field `@timestamp`. In real Kibana Discover select
that view, filter `labels.test_run: "<run>" and host.name: "vccunit1-fhs1"`, set the
UTC time range covering the run, and display `host.name`, `log.level`, `message`,
`event.id`, `service.name`. Capture and inspect an actual browser screenshot with
six events and levels visible, no credentials. This is additional Kibana proof;
the existing Grafana screenshot requirements and dashboard work are unchanged.

Stop only the runner's owned Filebeat process and owned loopback forwarding processes.
Keep the registry for the restart test. Cleanup/reapply validation must use a new
owned work directory and run ID, then assert six new events and zero extra hosts.
Delete only exact owned fixture directories after checking no Filebeat process uses
them. Retain evidence separately. Never reset ELK, delete PVCs, wildcard-delete
indices or alter unrelated containers. The supervisor must explicitly review any
removal of the exact owned index/template/policy/data view; default is retention.

Real filestream ingest, scoped bootstrap, clean registry restart, invalid-auth rejection,
separate-source reapply and inspected Discover capture passed. The supervisor verified
owned cleanup. Post-run VM memory was not recorded; see [validation](validation.md).
Fresh independent whole-goal review remains the controller's next stage.
