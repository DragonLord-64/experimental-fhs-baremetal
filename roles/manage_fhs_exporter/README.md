# manage_fhs_exporter

Installs the FHS Prometheus exporter archive into the FHS virtual environment and configures its service.

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `manage_exporters_exporter_file` | `/provision/files.d/external_archives/ska-mid-cbf-fhs-prometheus-exporter-main.tar.gz` | Controller-local archive |
| `fhs_exporter_port` | `9110` | Listener port |
| `fhs_exporter_log_level` | `DEBUG` | Log level |
| `fhs_exporter_venv_path` | `/opt/venvs/fhs` | Installation environment |

## Command and tags

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags manage_fhs_exporter
```

The site wrapper supplies `manage_fhs_exporter`; `tasks/main.yml` has no internal phase tags. The archive, virtual environment and hardware dependencies must already be available. Installation forces pip reinstallation; an unchanged run is not proven to avoid service changes. Physical exporter behavior was not validated by the synthetic platform check.
