# setup_fpga_host

Installs VFIO udev rules and optionally writes GRUB settings or programs BMC
firmware. SDK/package and venv installation belong to `manage_bittware_sdk`.
Select `--tags setup_fpga_host` in `playbooks/site.yml` for the default udev path.

| Variable | Default | Purpose |
|---|---|---|
| `fpga_update_grub` | `false` | Write GRUB config and run grub-mkconfig |
| `fpga_kernel_cmdline` | IOMMU + shared hugepage settings | Kernel command-line list |
| `fpga_update_bmc` | `false` | Also requires explicit `--tags setup_fpga_host,firmware` |
| `fpga_bmc_firmware_zip` | Empty | Approved local firmware archive |
| `fpga_bmc_firmware_version` | Empty | Expected BMC version |
| `fpga_bittware_user` | Ansible user | Unprivileged tooling owner |
| `fpga_bmc_cards` | `[0, 1]` | Cards to program |

The role never reboots. Pending boot changes are reported; old
`fpga_reboot_on_change`/`fpga_reboot_timeout` settings no longer trigger a reboot.
GRUB and firmware require their feature flags; selecting the whole role alone
does not enable either. The `never` tag is supplemented by an explicit firmware
tag check, so inherited site tags cannot enable firmware accidentally.

Shared DPDK settings: `fhs_hugepage_size=1G`, `fhs_hugepage_count=8`,
`fhs_hugepage_mount=/mnt/huge_1gb`. GRUB uses these defaults through
`fpga_kernel_cmdline`; keep custom command-line overrides consistent. The DPDK
role mounts this page size, and does not reserve pages itself.

Udev reload errors fail the run. The shipped rules invoke SDK-provided
`bittware-bind-vfio.sh`/`bittware-vfio-cleanup.sh`; their device permission behavior
cannot be verified without the SDK. Shared BittWare group membership alone does
not prove VFIO access. Offline rendering and a small DPDK build fixture do not
validate firmware, boot/kernel behavior, device access or physical hardware.
