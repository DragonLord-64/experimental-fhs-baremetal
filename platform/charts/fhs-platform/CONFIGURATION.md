# Platform settings

Set site overrides in `site-values.yaml`; install/upgrade commands are in the
[README](README.md). Full defaults: [values.yaml](values.yaml).

## Access

`global.hostname`, `scheme`, `urlPrefix`, `ingressClassName` and `tlsSecretName`
configure the shared ingress. The home and application links use the same prefix.
Supply the TLS Secret separately if needed.

## Home page

`landing.enabled` enables the home at the prefix root. NetBox, Grafana and Kibana
links come from deployment settings. Websites are checked every 60 seconds;
the page shows reachability and the last check time. Application logins stay
with each application.

Use `landing.introduction` for brief Markdown, or add
`--set-file landing.introduction=./introduction.md` to the Helm command.
Headings, paragraphs, bold and HTTP(S) links are supported; HTML is escaped.

```yaml
landing:
  links:
    - name: Documentation
      url: https://docs.example/installation
    - name: Jira
      url: https://jira.example/projects/HW
    - name: Confluence
      url: https://wiki.example/installation
```

`landing.timeoutSeconds` defaults to 4; `staleSeconds` to 150.
Optional `extraChecks` entries take `id`, `name`, public `url`, internal
`endpoint` and `expected` HTTP codes. Up to five are supported.
`netbox.enabled`, `grafana.enabled` and `logging.kibana.enabled` control the
managed links and application routes. Disabling Kibana also requires
`logging.filebeatSetup.enabled=false`.

## NetBox

Inventory 2.7.1, Prometheus SD 2.2.0 and Topology Views 5.0.0 install automatically
on NetBox 4.7.0. Topology Views is under `netbox/plugins/netbox_topology_views/`.
It displays recorded cables; uploaded custom icons use ephemeral pod storage.

Inventory synchronizes serials/tags and supports the `faulty` asset status.
Change-log retention is `netbox.changelogRetention` (default 90 days).

## Prometheus discovery

1. Create a read-only legacy NetBox API token with device-view access. Store it
   in Secret `fhs-netbox-discovery`, key `token`, in the installation namespace.
2. Add device multi-select field `prometheus_exporters` with choices `node` and
   `fhs`. Select installed exporters on active devices with primary IPv4s.
3. Enable `global.discovery.enabled` and remove migrated node/FHS targets from
   the static scrape list, retaining unrelated jobs.

Refresh defaults to 30s. `selector: tags` uses `node-exporter` / `fhs-exporter`
tags instead. Exporters must already be installed on the selected hosts.

## Logging

Filebeat setup is temporarily disabled by default because its image pull is
unavailable. Re-enable with `logging.filebeatSetup.enabled=true` when ready.

`logging.filebeatSetup.enabled` runs Filebeat setup on upgrades: templates,
system ingest pipelines, ILM and the `fhs-filebeat` Kibana data view. Retention
defaults to 30d for a new policy. Existing policy and data-view settings remain.
It installs no collector. `logging.filebeat.enabled` creates the limited
`filebeat_writer` account used by server shippers. Run setup before shipping logs.
