# manage_prometheus

Installs Prometheus and Node Exporter from controller-local archives, writes configuration and systemd services. This is host monitoring, separate from the Kubernetes platform release.

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `manage_prometheus_file_directory` | `/provision/files.d/external_archives` | Controller archive directory |
| `manage_prometheus_prometheus_tar` | `prometheus-3.12.0.linux-amd64` | Archive basename, without `.tar.gz` |
| `manage_prometheus_node_tar` | `node_exporter-1.11.1.linux-amd64` | Archive basename, without `.tar.gz` |
| `manage_prometheus_data_dir` | `/var/lib/prometheus` | Metrics storage |
| `manage_prometheus_prometheus_port` | `9090` | Listener port |
| `manage_prometheus_retention_size` | `15GB` | Retained size; task requires less than 200G |
| `manage_prometheus_retention_time` | `14d` | Retained history |
| `manage_prometheus_scrape_interval` | `15s` | Scrape interval |
| `manage_prometheus_evaluation_interval` | `15s` | Rule interval |
| `manage_prometheus_enable_auth` | `false` | Optional basic authentication |

See `defaults/main.yml`, `tasks/main.yaml` and `templates/` for service users and configuration. Supply any authentication hash privately; do not reuse a tracked example credential.

## Command and tags

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags manage_prometheus
```

Run from `/provision` with archives and private inventory available. The wrapper tag selects the whole role; internal `prometheus_config` marks only part of configuration and is not a standalone install path.
