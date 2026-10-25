# Experimental platform configuration

Use the [install / upgrade guide](README.md) for the shared commands. These
settings cover the experimental additions.

## Inventory discovery and HW home

The prefix root now serves a small public HW home linking to NetBox, Grafana and
Kibana. It contains no credentials or availability claims. Destination login
settings are unchanged. Set `landing.enabled=false` to omit it.

Both plugin installation paths pin Inventory `2.7.1` and Prometheus SD `2.2.0`
with wheel hashes. Discovery is opt-in to preserve existing static scrapes.
Before enabling it:

1. Create a dedicated NetBox service user with only device view permission,
   constrained to the selected active devices. No staff/superuser rights or
   write permissions. Issue a read-only **version 1 (legacy)** API token
   (`write_enabled=false`); this configuration uses `Authorization: Token`.
2. Store that token, without a newline, in the namespace-local Secret
   `fhs-netbox-discovery`, key `token`. Use a private file and
   `kubectl create secret generic ... --from-file=token=/private/token`;
   never put it in Helm values or shell arguments.
3. In NetBox create a **Multiple selection** custom field named
   `prometheus_exporters`, object type **DCIM > Device**, choices `node` and `fhs`,
   with an empty default. Select the exporters available on each active device:
   `node` uses port 9100; `fhs` uses port 9110. Set its primary IPv4 address.
   The exporters must already be running. An empty field selects nothing.
   Alternatively set `global.discovery.selector=tags` and use `node-exporter` /
   `fhs-exporter` tags. The field name, tags and refresh interval are configurable
   under `global.discovery`. IPv6-only discovery is not covered.
4. In site values set `global.discovery.enabled=true`. Replace the complete
   `prometheus.serverFiles.prometheus.yml.scrape_configs` list with your retained
   non-node jobs (for example `switch-telegraf`); remove migrated static node/FHS
   targets to avoid duplicates. Static configuration remains fully supported
   when discovery is disabled. Keep unmigrated static targets only for devices
   outside the selected inventory.

Prometheus reads the token from its Secret volume, calls the prefixed NetBox
API every 30s by default, and retains device/site/role plus `node_name` labels.
Metric `job` labels remain `node` / `fhs-exporter` for existing dashboards.
Removal, inactive status or clearing an exporter selection removes its target on the
next successful refresh without Helm changes. Failed refreshes may retain the
last successful targets; inspect Prometheus service-discovery errors.
The config reload sidecar reloads changed Prometheus configuration.

## Setup-only logging

`logging.filebeat.enabled` retains its original meaning: provision the limited
`filebeat_writer` account. It never installed a collector.
`logging.filebeatSetup.enabled` independently runs a bounded Filebeat `9.5.5`
setup Job (enabled in this umbrella; disabled by default in the standalone
logging chart). It loads the versioned template/mappings, Filebeat ILM policy,
system ingest pipelines, and a stable `fhs-filebeat` Kibana data view.
It has no inputs, host mounts, journals, DaemonSet or continuous publisher.
Only the setup Job receives the Secret-backed administrative credential;
remote shippers continue using `filebeat_writer`.

The existing Ansible Filebeat role uses the default versioned `filebeat-*`
destination with template installation disabled. Setup must finish before those
writers start. The older scoped `filebeat-fhs-one-9.5.5` bootstrap has its own
higher-priority template/policy/alias; this setup leaves those resources alone.
No dashboards are imported. Existing template, policy and same-ID data view
are preserved. `logging.filebeatSetup.retention` defaults to `30d` for a new ILM
policy; it does not overwrite an existing policy's retention.

Both logging service-user setup and Filebeat setup Jobs use `.Release.Revision`:
they run on **every** same-release upgrade, including a discovery-only change.
They are bounded Jobs; that does not imply unrelated workload rollouts.

## Minimal same-release update

Before upgrading, retain the existing site values, release revision, private
Secret backup, PostgreSQL backup and stateful-volume snapshots. Verify restore
procedures. Helm rollback cannot reverse NetBox database migrations or restore
Elasticsearch data, ILM policies or credentials.

For the existing profile, with the complete private `site-values.yaml` retained:

```bash
helm diff upgrade mid-cbf-hw ./fhs-platform \
  --kube-context "$KUBE_CONTEXT" --namespace hw-management \
  -f site-values.yaml --suppress-secrets
helm upgrade mid-cbf-hw ./fhs-platform \
  --kube-context "$KUBE_CONTEXT" --namespace hw-management \
  -f site-values.yaml --dry-run=server --hide-secret
helm upgrade mid-cbf-hw ./fhs-platform \
  --kube-context "$KUBE_CONTEXT" --namespace hw-management \
  -f site-values.yaml --wait --wait-for-jobs --timeout 20m
```

The first command requires the existing Helm diff plugin. Review the preview:
expect NetBox plugin consumers, Prometheus/config reload, new landing resources
and the bounded logging Jobs. PostgreSQL, Valkey, Grafana, Telegraf, Elasticsearch
and Kibana pod templates and PVCs should stay stable. Do not uninstall, delete
PVCs, reset credentials or run a blanket rollout. Keep the site's hostname and
prefix in its private values. For an application rollback after assessing the
migration/data limits, use `helm rollback mid-cbf-hw PREVIOUS_REVISION` with the
same explicit context/namespace and wait flags. These are operator instructions;
no hardware deployment is established by an offline render.

## Topology Views

The public-image startup and optional image recipe include hash-pinned
`netbox-topology-views==5.0.0` for NetBox `4.7.x`. Web, worker and housekeeping
share the plugin configuration. Startup prepares writable per-pod
`static/netbox_topology_views/img`; web runs the existing entrypoint migrations
and collects plugin static assets before serving. Custom image uploads in this
emptyDir are ephemeral; no persistent custom-icon store is configured.
Open `PREFIX/netbox/plugins/netbox_topology_views/` after login. Maps use NetBox
cable records; this does not discover physical cabling.

[Focused checks and package evidence](../../../ops/platform/topology-views/README.md).
