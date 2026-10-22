# Manage FHS Exporter

This role installs and configures the FHS Prometheus Exporter. It automates the deployment of system dependencies, creates necessary directory structures, and extracts Prometheus aggregation and threshold rules from a source archive. The exporter is installed into a managed Python virtual environment and configured as a systemd service to provide telemetry.

The FHS exporter repo contains all necessary files and configurations for this role: https://gitlab.com/ska-telescope/ska-mid-cbf/host-software/ska-mid-cbf-fhs-prometheus-exporter

## Requirements

The role requires `python3`, `python3-pip`, and `python3-venv` to be installed on the target system to manage the virtual environment and execute the exporter.


## Variables

### 1. Installation Source
These variables define the location of the exporter source archive on the Ansible control host.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `manage_exporters_exporter_file` | `"/provision/files.d/external_archives/ska-mid-cbf-fhs-prometheus-exporter-main.tar.gz"` | The absolute path on the control host to the compressed exporter source archive. |

### 2. Service Configuration
These variables control the operational parameters of the exporter service.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `fhs_exporter_port` | `9110` | The network port on which the exporter post results. |
| `fhs_exporter_log_level` | `"DEBUG"` | The logging verbosity level for the exporter service. |
| `fhs_exporter_venv_path` | `"/opt/venvs/fhs"` | The filesystem path for the Python virtual environment where the exporter is installed. |

## Handlers

The following handlers are triggered during the installation process to ensure configuration changes are applied:

- **Restart Prometheus**: Restarts the Prometheus service when aggregation rules are updated.
- **Restart Exporter**: Restarts the FHS Exporter service when threshold rules or the binary are updated.
- **Reload Systemd Daemon**: Reloads the systemd manager configuration when the service unit file is updated.

## License

BSD-3-Clause