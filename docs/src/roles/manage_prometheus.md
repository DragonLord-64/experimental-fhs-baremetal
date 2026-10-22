# Manage Prometheus and Node Exporter

This role installs and configures the Prometheus monitoring stack along with the Node Exporter. It manages the deployment of binary artifacts from a local control host, sets up the necessary directory structures, and configures the Prometheus service with custom retention policies, scrape intervals, and authentication settings. The role also installs and configures `node_exporter` as a systemd service to collect system-level metrics.

The Prometheus install is configured to dynamically add/configure rule and aggregation based on a configuration directory defined in the prometheus config yaml. For more information on prometheus see https://github.com/prometheus/prometheus.

Prometheus is configured to scrape the exporter directly on the local port. For more information on the node exporter see https://github.com/prometheus/node_exporter


## Requirements

The role requires the following source artifacts to be present in the `manage_prometheus_file_directory` on the Ansible control host:
- The Prometheus compressed tarball.
- The Node Exporter compressed tarball.

The target system must have `systemd` for service management.

## Variables

### 1. Versioning & Source Paths
These variables define the versions and local file locations for the monitoring binaries.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `manage_prometheus_file_directory` | `"/provision/files.d/external_archives"` | The directory on the control host containing the monitoring archives. |
| `manage_prometheus_apt_version` | `"2.45.3+ds-2ubuntu0.3"` | The specific APT version of Prometheus (if using system packages). |
| `manage_prometheus_prometheus_tar` | `"prometheus-3.12.0.linux-amd64"` | The filename (prefix) of the Prometheus tarball. |
| `manage_prometheus_node_tar` | `"node_exporter-1.11.1.linux-amd64"` | The filename (prefix) of the Node Exporter tarball. |

### 2. Authentication Settings
These variables control access security for the Prometheus web interface.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `manage_prometheus_enable_auth` | `false` | Boolean flag to enable or disable basic authentication. |
| `manage_prometheus_user_cred` | `"$2b$12$..."` | The hashed password string used for authentication. |

### 3. Prometheus Operational Settings
These variables configure the core behavior of the Prometheus engine.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `manage_prometheus_prometheus_port` | `9090` | The port on which the Prometheus server listens. |
| `manage_prometheus_retention_size` | `15GB` | The maximum amount of storage Prometheus is allowed to use. |
| `manage_prometheus_retention_time` | `14d` | The maximum duration to retain time-series data. |
| `manage_prometheus_scrape_interval` | `15s` | The frequency at which Prometheus pulls metrics from targets. |
| `manage_prometheus_evaluation_interval`| `15s` | The frequency at which Prometheus evaluates alerting rules. |

## Execution Tags

| Tag | Description |
| :--- | :--- |
| `prometheus_config` | Specifically handles the creation of `/etc/prometheus` and the application of configuration templates. |

## Handlers

- **Restart Prometheus**: Restarts the Prometheus service when the main configuration or service file is updated.
- **Restart Node**: Restarts the Node Exporter service when its configuration or service file is updated.

## License

BSD-3-Clause