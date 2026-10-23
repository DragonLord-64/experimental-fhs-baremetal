# Umbrella chart checks

Portable launch files live in [fhs-platform](../../../platform/charts/fhs-platform/README.md).
Development checks stay here; no cluster is contacted.

```bash
python3 -m unittest discover -s ops/platform/umbrella -p 'test_*.py' -v
helm lint platform/charts/fhs-platform --namespace mid-cbf-monitoring-test
helm lint platform/charts/elasticsearch-kibana
python3 -m unittest discover -s ops/platform/logging -p 'test_*.py' -v
```

The eight umbrella tests render the actual bundled dependencies: namespaced
resources, internal Services/backends, storage/secret references, all app base
paths/probes, nested/empty prefix, arbitrary namespace/host, external PostgreSQL,
invalid inputs, six dashboard unpack/navigation and a copied-folder render.
Helm's server lookup is exercised against a temporary loopback-only mock API;
every credential is preserved and a missing key fails. The test needs permission
to bind loopback sockets. It never writes to the mock API or contacts Kubernetes.

2026-10-23: all eight passed, plus both chart lints and the six existing logging
tests. No hardware-cluster deployment, image pull, browser, TLS, storage binding,
database migration, telemetry or greater-cluster capacity test was performed.

Fresh independent review found no actionable issues; seven cases passed again,
with the loopback mock blocked by that review sandbox. The implementer's full
eight-case run passed with loopback permission. A separate temporary container
using the cached pinned Grafana image verified `gzip`, `sed`, `wget`, `basename`
and prefix substitution as UID 472, with no network, host mounts or writable root.

Dependencies retain upstream archives; `Chart.yaml` / `Chart.lock` pin sources
and versions. The local Elasticsearch/Kibana 0.5.1 adds opt-in shared URL helpers;
its default standalone paths remain unchanged. The archive inside the umbrella
must be repackaged after source changes:

```bash
helm package platform/charts/elasticsearch-kibana \
  --destination platform/charts/fhs-platform/charts
```

Dashboard archives are deterministic gzip copies of the six self-contained
`platform/grafana_dashboards/generated/*.json` files (gzip mtime 0). No dashboard
generator or source-tree access is needed at runtime. The Grafana init container
unpacks them into an emptyDir and adjusts `/d/` navigation to the app prefix;
queries and inventory are unchanged. Dashboard/model compatibility with real
hardware labels remains an operator check. Update the archive checksum in
`grafana.podAnnotations` when refreshing assets so upgrades rerun the init.

[Archive hashes](archives.sha256) record the packaged delivery dependencies and
dashboard assets. The semantic checker derives routes from the shared prefix;
its cluster-resource, exposure, hostPath and backend checks retain the screen
baseline. The route suffix check changed only for the user's later prefix requirement.
