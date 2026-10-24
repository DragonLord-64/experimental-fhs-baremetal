# Platform deployment and access

`platform/` contains portable cluster values and the bundled FHS platform chart.
Review storage classes, ingress, telemetry targets and private credentials for
the intended cluster before deployment.

Copy the whole `platform/charts/fhs-platform/` directory for a single-release
installation. Its README contains build/load instructions for the pinned NetBox
Inventory image, namespace/prefix selection, upgrade credentials and persistent
storage. Dependencies and the six runtime dashboards are included; deployment
does not require a lab generator or test checkout.

The root `platform/README.md` documents the older separate-release procedure.
Keep existing release names, credentials and volumes on upgrades. Back up NetBox
before plugin activation or schema migrations; a Helm rollback cannot undo
those migrations. Verify login, static assets, routing and storage in the chosen
cluster before changing telemetry destinations.

Prometheus scrapes server/node exporters and Telegraf; Grafana queries those
metrics. Filebeat forwards logs to Elasticsearch and Kibana queries the log
store. Inventory, synthetic fixtures and missing observations have distinct
meanings; an absent metric does not prove healthy hardware.
