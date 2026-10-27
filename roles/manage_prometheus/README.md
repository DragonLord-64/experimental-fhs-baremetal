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

Run from `/provision` with archives and private inventory available. The wrapper tag selects the whole role; there are no internal phase tags.

Changed archives notify the matching service, including same-path binary
replacement. Configuration is checked with the installed promtool before writing.
Pending changes restart once before the final start/enable tasks; unchanged runs
avoid restarts and reruns recover stopped services. Node Exporter retries failures.
The Prometheus port variable configures its actual listener.

Configuration is root-owned and readable by the Prometheus group. Services use
separate unprivileged accounts. Authentication is off by default and both services
listen on all addresses; use the deployment's approved access controls. Enabling
basic auth requires a privately supplied bcrypt hash; there is no example hash.
Basic auth alone does not encrypt traffic: terminate TLS in the approved ingress
or proxy. Node Exporter has no authentication configuration in this role.

Real pinned binaries/configuration and process starts are checked in a disposable
container. The service-manager fixture does not establish systemd sandboxing,
automatic failure restart or boot behavior. No monitoring feature or hardware
reading correctness is claimed.
