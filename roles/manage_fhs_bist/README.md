# Manage FHS BIST

Installation/configuration placeholder for BIST (Built-in Self Test), not a
production-ready application. It writes the unit but does not enable/start it,
run pytest or require traces/results during installation. Starting the supplied
unit runs hardware tests and requires separate explicit user authorization.

Supply a reviewed archive with pinned `requirements.txt`; deployment installs it
without resolving a new requirements file. Python venv support and the configured
service account/group must already exist. Source/archive preparation remains on
the Ansible controller. Installation tests use an inert archive, not hardware
results. Real application dependencies and service execution remain unvalidated.

## Configuration Variables

Hardware defaults are in `defaults/main.yml`; current application/build paths and identity are in `vars/main.yml` (role vars override inventory). Review them before use; task/extra vars can override them.

### 1. Hardware Mappings (Inventory Specific)
These variables map physical hardware to the BIST software. These **must** be overridden in your inventory to match the specific hardware of each server.

| Variable Name | Description | Example |
| :--- | :--- | :--- |
| `fpga_card0_sn` | Serial number for FPGA card 0 | `8190639` |
| `fpga_card1_sn` | Serial number for FPGA card 1 | `8190638` |
| `fpga_card0_bdf_ark` | PCI BDF for FPGA card 0 Arkville function | `"01:00.0"` |
| `fpga_card1_bdf_ark` | PCI BDF for FPGA card 1 Arkville function | `"81:00.0"` |
| `fpga_card0_bdf_detri` | PCI BDF for FPGA card 0 DeTRI function | `"01:00.1"` |
| `fpga_card1_bdf_detri` | PCI BDF for FPGA card 1 DeTRI function | `"81:00.1"` |
| `terabox_nic0_sn` | Serial number of the Terabox NIC | `MT2253J12826` |
| `terabox_nic0_bdf` | PCI BDF for the Mellanox 200G NIC | `"c1:00.0"` |
| `nvme0_bdf` | PCI BDF for NVME drive 0 | `"84:00.0"` |
| `nvme1_bdf` | PCI BDF for NVME drive 1 | `"86:00.0"` |
| `nvme0_device_name` | Linux device name for NVME drive 0 | `nvme0n1` |
| `nvme1_device_name` | Linux device name for NVME drive 1 | `nvme1n1` |
| `terabox_lan0_iface` | Ethernet interface name for LAN0 (2.5G) | `enp2s0f0` |
| `terabox_nic0_iface` | Ethernet interface name for Mellanox NIC (200G) | `enp1s0np0` |

### 2. Repository & Service Configuration
Controls where the software is pulled from and how the service runs.

| Variable Name | Description | Example |
| :--- | :--- | :--- |
| `repo_url` | The URL for the BIST repository | `https://gitlab.com/...` |
| `repo_version` | Version/Branch/Commit to checkout | `main` |
| `bist_user` | The BIST service user | `ubuntu` |
| `bist_group` | The BIST service group | `bittware` |

### 3. Installation Paths (Server Side)
Defines the directory structure on the target FHS server.

| Variable Name | Description | Example |
| :--- | :--- | :--- |
| `app_dir` | Base installation directory | `/opt/bist` |
| `venv_dir` | Path to the Python virtual environment | `/opt/bist/fhs-bist-venv` |
| `test_inputs_dir` | Directory for test input files | `/opt/bist/test_input` |
| `log_dir` | Directory for application logs | `/var/log/bist` |
| `traces_dir` | Directory for execution traces | `/var/log/bist/traces` |
| `results_dir` | Directory for test results | `/var/log/bist/results` |

### 4. Build & Archive Paths (Controller Side)
Defines where the BIST archive is built and stored on the machine running Ansible.

| Variable Name | Description | Example |
| :--- | :--- | :--- |
| `build_dir` | Temporary build directory on controller | `/tmp/bist` |
| `repo_dir` | Local directory where repo is checked out | `/tmp/bist/repo` |
| `archive_name` | Name of the generated tarball | `bist-main.tar.gz` |
| `archive_dir` | Directory where the final archive is stored | `/tmp/bist/archive` |
| `archive_path` | Full path to the final BIST archive | `/tmp/bist/archive/...` |

## Dependencies

None.

## License

BSD-3-Clause