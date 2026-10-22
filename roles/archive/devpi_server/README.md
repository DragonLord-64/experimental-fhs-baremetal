# midcbf.fhs.devpi_server

devpi-server PyPI mirror, installed into a dedicated venv at
`/opt/devpi-venv`, data under `/opt/devpi`, run as `devpi` user under
systemd.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `devpi_user` / `devpi_group` | `devpi` | Service account |
| `devpi_data_dir` | `/opt/devpi` | `--serverdir` |
| `devpi_venv` | `/opt/devpi-venv` | Where devpi is installed |
| `devpi_python` | `/usr/bin/python3` | Interpreter to create venv from |
| `devpi_host` / `devpi_http_port` | `0.0.0.0:3141` | Listen address |
| `devpi_packages` | `[devpi-server, devpi-web, devpi-client]` | Pinned versions advised |

Tags: `devpi_server`, `install`, `config`.
