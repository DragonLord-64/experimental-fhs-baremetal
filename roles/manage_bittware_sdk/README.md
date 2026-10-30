# Manage Bittware SDK

The site provisioning workflow now uses `manage_users`
for accounts, system SDK and all BittWare environments. This standalone role
remains for existing direct callers; use `--tags manage_users` with `site.yml`.

Installs the Bittware SDK onto a FHS system. This role installs required system packages and utilizes `bw_pip.py` to install the SDK into managed Python virtual environments.

## Requirements

The role requires `python3`, `python3-pip`, and `python3-venv` to be installed on the target system.

## Variables

### 1. SDK Installation
These variables control how the Bittware SDK package is installed.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `fpga_bittware_sdk_deb` | `""` | Path to a local `.deb` file. If provided, installs via this file. |
| `fpga_bittware_sdk_package` | `"bittware-sdk"` | The name of the SDK package to install. |
| `fpga_bittware_sdk_root` | `"/usr/share/bittware-sdk"` | The installation root directory for the SDK. |
| `fpga_bittware_group_gid` | `666` | The GID for the Bittware group. |
| `fpga_bittware_group` | `"bittware"` | The name of the Bittware group. |

### 2. System Dependencies
These variables manage system-level package installation and OS validation.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `fpga_apt_packages` | `[python3, python3-pip, ...]` | List of APT packages required on every FPGA host. |
| `fpga_approved_os` | `"Ubuntu 24.04"` | Informational only; the role currently does not enforce this value. |

### 3. Virtual Environment Management
These variables are used to manage Python environments via `bw_pip.py`.

| Variable Name | Description |
| :--- | :--- |
| `venvs` | A list of dictionaries defining virtual environments to manage. |
| `users_setup_venvs` | Boolean flag to trigger virtual environment setup. |
| `fpga_update_bittware_sdk` | Boolean flag to trigger the SDK installation task. |



## Dependencies

- The bittware SDK deb package available on the ansible host

## License

BSD-3-Clause
Shared identity: set `fhs_bittware_group` and `fhs_bittware_group_gid` consistently
for users, SDK and runner (defaults `bittware`, `666`). Legacy `fpga_bittware_group`
and `fpga_bittware_group_gid` default to these shared values; do not override them
inconsistently. A GID change on an existing server needs ownership review.

SDK venv packaging and installation run as each venv's owner. The system package
step does not set up the runner account/venv. `fpga_update_bittware_sdk` and
`users_setup_venvs` default false. A missing SDK skips venv SDK installation.
The focused fixture is a minimal deb with an installer/entrypoint; real installer,
SDK commands and FPGA behavior are unvalidated.
