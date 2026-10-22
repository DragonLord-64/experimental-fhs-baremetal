# Manage DPDK, Arkville, and DOCA

This role installs and configures a high-performance networking stack. It orchestrates the installation of the NVIDIA DOCA framework, Arkville data-mover drivers, and a DPDK (Data Plane Development Kit) environment. Finally, it compiles the Arkville high-performance application suite. When installed on an FHS, this setup enables the data path from the FPGA, to the memory, through the CPU, and out the NIC.

## Requirements

The role requires access to a local file storage path (engine) containing the necessary compressed source bundles and `.deb` artifacts. The target system must have build essentials and sufficient disk space for compiling DPDK and application suites.

DPDK download: https://core.dpdk.org/download/
DPDK Documentation: https://doc.dpdk.org/guides/prog_guide/build-sdk-meson.html

Arkville download (NRC ONLY): https://git-collab.nrc-cnrc.gc.ca/haa/fsa/fpga/external/arkville/-/tree/main/archive?ref_type=heads
Arkville documentation (NRC ONLY): https://git-collab.nrc-cnrc.gc.ca/haa/fsa/fpga/external/arkville/-/tree/main/archive?ref_type=heads

DOCA Download: https://developer.nvidia.com/doca-downloads
DOCA documentation: https://developer.nvidia.com/networking/doca/getting-started

## Variables

### 1. DPDK Infrastructure
These variables define where the custom patched DPDK source code is located on the local engine.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `dpdk_local_path` | `"/provision/files.d/"` | The local directory on the engine containing the DPDK source bundle. |
| `dpdk_tarball_filename` | `"dpdk.tar.gz"` | The filename of the compressed patched DPDK source tree. |

### 2. Arkville Installation
These variables manage the extraction and compilation of the Arkville driver and application components.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `arkville_release` | `"25.11"` | The specific version of the Arkville release. |
| `arkville_local_path` | `"/provision/files.d/arkville/archive"` | The local path containing the Arkville release artifacts. |

### 3. NVIDIA DOCA Configuration
These variables control the installation of the NVIDIA DOCA framework via local Debian packages.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `doca_local_path` | `"/provision/files.d/"` | The local directory containing the DOCA `.deb` file. |
| `doca_deb_filename` | `"doca-host_3.3.0-088000-26.01-ubuntu2404_amd64.deb"` | The specific DOCA Debian package filename to install. |

**Note** MFT is installed through doca and is required for [manage_exporters](manage_exporters.md) ansible role.

## Execution Tags

Use the following tags to run specific segments of the installation pipeline:

| Tag | Description |
| :--- | :--- |
| `install` | Runs the entire installation pipeline. |
| `prereqs` | Installs necessary system dependencies and prepares the environment. |
| `doca` | Installs the NVIDIA DOCA framework. |
| `arkville` | Extracts the Atomic Rules Arkville driver trees. |
| `dpdk` | Builds and installs the DPDK framework with Arkville extensions. |
| `arkville_apps` | Compiles the final Arkville high-performance application suite. |

## License

BSD-3-Clause