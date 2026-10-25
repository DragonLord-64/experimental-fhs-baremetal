# Validation — 2026-10-24

Full delivered-chart acceptance passed at `2026-10-25T05:03:29Z` on dragonvm's
existing `fhs-test` cluster, namespace `fhs-discovery-portal-test`, release
`mid-cbf-hw`, prefix `/mid-cbf-hw`. No hardware or official SKA repository changed.

Evidence: ignored
`ops/agent-pipeline/runs/platform-discovery-portal-setup-supervised-20261024/validation/acceptance.json`;
SHA-256 `ba9b9bf34f9a4b26120885a3fbc541b5e39ce964a11831c3f8a3aa6f72600b60`.
The full report and prior attempts also remain on dragonvm under its recorded
`/tmp/fhs-discovery-acceptance-*` directory. Credentials/diagnostics remain private.
All delivered runtime/chart/importer source hashes match the successful snapshot;
subsequent differences are documentation and additional local harness tests.

- Installed committed private baseline `8fe1d1788ff87def0824e5dfa9115a02aa3cebeb`,
  seeded real NetBox through native Ansible, then upgraded the same full release.
  Native inventory/history checks: **69 before + 69 after**; native FRU checks:
  **16 before + 16 after**. Only synthetic discovery/IPMI fixtures were used.
- Prometheus scraped real synthetic listeners on ports 9100/9110 using a
  read-only token and `prometheus_exporters` multi-select filter. Independent
  deselection, rename, inactive status, clearing, reselection and deletion
  refreshed correctly with **zero Helm changes** during that lifecycle.
- Actual ingress and local assets passed for HW home, NetBox, Grafana and Kibana.
  Browser inspection verified the landing cards and all three rendered login pages.
- Real Filebeat setup completed, installing the versioned template, 30-day ILM
  policy, system pipelines and stable Kibana data view. The limited writer
  ingested one event; writes outside `filebeat-*` and security administration
  were denied. No persistent Filebeat collector or host mount was installed.
- Repeat Helm upgrade preserved the event, custom policy/dashboard, data-view
  registry and setup definitions. All pod/PVC/credential identities stayed stable
  during reapplication. Across the baseline upgrade, only NetBox web/worker and
  Prometheus templates changed; PostgreSQL, Valkey, Grafana, Telegraf,
  Elasticsearch and Kibana templates and pod identities stayed unchanged.
  Original asset/history/journal IDs and payloads were preserved.

Offline checks passed: 13 discovery/harness tests, 54 importer regressions
(with real Ansible; no skips), ten umbrella, six logging and six source-boundary
checks; both Helm lints, all 13 archive hashes and `git diff --check`.
The incomplete old local temporary Ansible runtime failed to import Ansible;
the complete 54-test suite passed in the verified dragonvm runtime.

Earlier attempts exposed actual NetBox service-host rejection and a landing
nginx alias error; both are fixed and exercised live. The synthetic exporter
needed a proper metrics Content-Type. Harness repairs covered token lookup,
relative Grafana assets and prefixed Kibana URL joining. Interrupted/failed
attempt evidence was retained. Native results were reused for later harness-only
repairs only after verifying identical chart/importer hashes and NetBox pod UIDs.
The implementation pipeline remained paused; the supervisor completed these checks.

After validation, the owned candidate is scaled to zero with its PVCs/Secrets
retained, and the four previously paused NetBox web/worker deployments are restored.

Limits: HTTP lab ingress only; no production deployment, physical discovery,
exporter installation on hardware, TLS validation or journald collection test.
Tag selection and other prefixes have render coverage; this live run used the
custom field. Discovery is opt-in for an existing deployment, using the documented
legacy read-only token. Keep existing site values and remove migrated static
scrapes explicitly. Helm rollback cannot reverse database migrations or data loss.
