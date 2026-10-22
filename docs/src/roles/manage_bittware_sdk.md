# Manage Bittware SDK

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
| `fpga_approved_os` | `"Ubuntu 24.04"` | Validates the host OS version. Set to `""` to skip. |

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