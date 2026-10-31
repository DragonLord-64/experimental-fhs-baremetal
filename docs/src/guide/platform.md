# Platform deployment and access

`platform/` contains portable cluster values and the bundled FHS platform chart.
Review storage classes, ingress, telemetry targets and private credentials for
the intended cluster before deployment.

Copy the whole `platform/` directory for installation and credential export. Its README contains installation commands, namespace/prefix selection,
credential export and persistent storage settings. Dependencies and the six runtime dashboards are included.

The root `platform/README.md` links the platform installation and endpoint settings.
Keep existing release names, credentials and volumes on upgrades. Back up NetBox
before plugin activation or schema migrations; a Helm rollback cannot undo
those migrations. Verify login, static assets, routing and storage in the chosen
cluster before changing telemetry destinations.

Prometheus scrapes server/node exporters and Telegraf; Grafana queries those
metrics. Filebeat forwards logs to Elasticsearch and Kibana queries the log
store. Inventory, synthetic fixtures and missing observations have distinct
meanings; an absent metric does not prove healthy hardware.

(export-ansible-settings)=

## Export Ansible settings

After Helm installation, run on the cluster management machine:

```bash
python3 platform/charts/export-platform.py
```

Copy its local `platform/charts/platform-export/platform-secrets.yml` to
`/provision/files.d/credentials/platform-secrets.yml` on the Ansible controller,
and `platform-endpoints.yml` to `/provision/files.d/platform-endpoints.yml`.
Those paths are inside the provisioning container's resource mount.

```bash
ansible-vault encrypt /provision/files.d/credentials/platform-secrets.yml
```

On the Ansible host, from its checkout, verify endpoints using the host resource
path (the Compose default is shown):

```bash
python3 platform/charts/export-platform.py \
  --check-endpoints /shared/midcbf_provision_files.d/platform-endpoints.yml
```

Copy the endpoints file's `netbox_url` into `api_endpoint` in
`inventory/dev_env/netbox-inv.yml`. Inventory and import/export playbooks share
the Vault file's token. Distribution and Filebeat settings read the endpoints
file; local filesystem paths stay in inventory. The exporter checks connectivity
and reuses credentials, with no rotation or automatic copying.
