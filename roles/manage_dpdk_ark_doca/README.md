# manage_dpdk_ark_doca

This role installs dpdk, DOCA, and arkville. This is required to move data over the pcie and out the NIC card.

## Variables
`dpdk_local_path`: directory of dpdk tar.gz file

`dpdk_tarball_filename`: name of dpdk tar.gz file


`arkville_release` : arkville release version
`arkville_local_path` : path to arkville release file


`doca_local_path` : directory of doca package
`doca_deb_filename` : doca package file name

Select `--tags manage_dpdk_ark_doca` in `playbooks/site.yml`. Supply all three
approved controller-local artifacts before running. The role hashes their
contents, release, kernel, dependency list, hugepage settings and
`dpdk_build_revision`. An unchanged successful installation with its configured
outputs present skips the entire procedure. Source/settings changes, a missing
output, absent success state or `dpdk_force_rebuild=true` run the full procedure
from clean Arkville/DPDK trees. Success is recorded only after every step and
output check completes; a failed run leaves no success state. All input changes
are clean-build triggers. Increment `dpdk_build_revision` after changing local
build commands. Default state: `/var/lib/fhs/dpdk-success.sha256`; default required
output: `/usr/local/bin/dpdk-testpmd` (`dpdk_install_outputs`). This is an installation
check, not continuous integrity monitoring of every installed library.

Build trees are root-owned and not writable by development accounts because
privileged installers execute their contents. Use only approved artifacts.
APT errors fail the run. Old build-tree uninstall scripts are not executed as
root: previous trees may have been user-writable. Clean builds replace the source
trees and reinstall outputs; they do not prune obsolete system libraries.

Shared with `setup_fpga_host`: `fhs_hugepage_size=1G`, `fhs_hugepage_count=8`,
`fhs_hugepage_mount=/mnt/huge_1gb`. The FPGA role reserves pages only with explicit
GRUB opt-in; this role mounts them. `dpdk_manage_hugepages=false` is for isolated
userland build fixtures only. No boot change or reboot is performed here.
A small C/Meson fixture tests installation state, not real DOCA/Arkville bundles,
NIC/FPGA behavior, kernel drivers or actual hugepage reservation.
