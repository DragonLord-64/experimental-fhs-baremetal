# manage_fhs_exporter

Installs the FHS Prometheus exporter archive into the FHS virtual environment and configures its service.

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `manage_exporters_exporter_file` | `/provision/files.d/external_archives/ska-mid-cbf-fhs-prometheus-exporter-0.0.5-rc3.tar.gz` | Controller-local archive |
| `fhs_exporter_port` | `9110` | Listener port |
| `fhs_exporter_log_level` | `DEBUG` | Log level |
| `fhs_exporter_venv_path` | `/opt/venvs/fhs-exporter` | Installation environment |

## Command and tags

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags manage_fhs_exporter
```

The site wrapper supplies `manage_fhs_exporter`; there are no internal phase tags.
Supply a reviewed controller-local release archive. The role installs Python venv
support, pciutils, sudo, ipmitool, ethtool and MFT; MFT needs an approved vendor package source.
`fhs_exporter_apt_packages` can select already approved dependencies. Pip uses the
host's configured index; Poetry's project index settings do not configure pip.
The public 0.0.5-rc3 package declares Click, prometheus-client and PyYAML.

The archive checksum and a working console `--help` check gate installation.
Unchanged runs skip pip; changed archives reinstall and restart the exporter.
The checksum is recorded only after installation/import success. The root-owned
cache remains in `/var/cache/fhs-exporter`. A stopped service is started on rerun.

The default dedicated venv replaces the shared `/opt/venvs/fhs` default. Root
executes the exporter for hardware access: never point it at code or an environment
writable by development users. BittWare SDK commands must be installed on the
service PATH by the separate SDK role. The role rejects non-root-owned or group/other-writable files and directories
before executing existing venv code. Existing shared environments are not deleted or
recursively taken over. The listener retains the package's all-address binding;
restrict access through your deployment's existing access policy. No authentication
is supplied by this role. Hardware privilege reduction requires separate validation.

Prometheus discovery/rules are still written locally. Rule changes restart
Prometheus only if its service is installed; the exporter does not require a local
Prometheus service. Threshold rules belong to Prometheus, not the exporter.

Stage-5 checks cover real package installation/imports, configuration, process
startup and reruns without requesting metrics. Startup itself enumerates PCI
devices with the package's lspci call; no command output is tested as hardware data. MFT, hardware readings, exporter
correctness and real systemd operation remain unvalidated.
