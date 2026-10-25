# Topology Views check

[Issue #12](https://github.com/DragonLord-64/experimental-fhs-baremetal/issues/12).
[Upstream v5.0.0](https://github.com/netbox-community/netbox-topology-views/tree/v5.0.0)
supports NetBox 4.7.x. On 2026-10-24, PyPI JSON and the downloaded wheel agreed:

- `netbox_topology_views-5.0.0-py3-none-any.whl`
- SHA-256 `afe03396b67e8ed16ae2ad43d13bd8380f48cc0ffd1621259b6a60fa21f7170f`
- No `Requires-Dist` or `Requires-Python` metadata. Source imports use the standard
  library, NetBox and its existing Django/filter/tables/DRF/taggit dependencies;
  no extra dependency package is required by this release. Startup retains
  `--no-deps --require-hashes`.

Offline checks:

```bash
python3 -m unittest discover -s ops/platform/topology-views -v
helm lint platform/charts/fhs-platform
```

Controller-only live check (worker must not execute):

```bash
ops/platform/topology-views/smoke.py --report /tmp/fhs-topology-views-smoke.json
```

Uses the existing `mid-cbf-hw` Helm release in namespace
`fhs-discovery-portal-test` on dragonvm. NetBox Deployment/Service: `fhs-netbox`.
Transfers only chart and check sources when orchestrated remotely. Requires Helm, minikube, Python
with PyYAML and retained private lab values at
`/tmp/fhs-discovery-acceptance-7fe5ixpb/lab-values.yaml`. Never prints values.
The full delivered chart is upgraded with existing workload scales retained;
only NetBox web/worker, PostgreSQL and Valkey start. Unrelated setup Jobs are
omitted and CronJobs suspended during the check. Original scales and CronJob
suspension are restored afterward. PVCs and Secrets are retained.

The check reports timings, installed version, migration completion, writable
static directory, an authenticated topology page through Django's test client,
and actual CSS/JS responses over a service port-forward. Two synthetic devices
and one cable use existing lab site/role/type; their connection must appear in
the page's actual topology JSON. The fixture and session changes roll back in
one transaction, including on failure. No fixture accumulates between runs.
No physical discovery or browser visual validation is claimed.

2026-10-24: three focused tests, six existing discovery chart contracts and Helm
lint passed. Supervised live smoke passed in 78.42s (upgrade/readiness 57.83s;
plugin probe 12.59s): version 5.0.0, migrations, authenticated topology connection,
CSS/JS, PVC/credential preservation and original scale restoration. The original
blocked run is retained; recovery evidence is under ignored
`ops/agent-pipeline/runs/netbox-topology-recovery-20261024/`. The check uses the
named topology route and excludes Helm release-history Secrets from the
application credential comparison; private command diagnostics are retained.
The [previous full acceptance](../discovery-portal-setup/VALIDATION.md) remains
baseline evidence; discovery, logging and native importer sources are untouched.
