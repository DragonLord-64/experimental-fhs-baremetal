# Setup FPGA Host

Configure a Bittware FPGA host: apt prerequisites, VFIO udev rules,
GRUB kernel cmdline, Bittware SDK, per-user venvs, BMC firmware.

Destructive operations (GRUB, SDK, BMC firmware) are off by default and
gated by feature-flag vars. BMC firmware also carries the `never` tag —
opt in explicitly with `--tags fpga,firmware`.

## Variables (high-traffic)

| Var | Default | Purpose |
|---|---|---|
| `fpga_kernel_cmdline` | `[iommu=pt, amd_iommu=on, hugepages=8, hugepagesz=1G, default_hugepagesz=1G]` | GRUB cmdline (list) |
| `fpga_bittware_sdk_deb` | `""` | Local path to SDK .deb (required for SDK install) |
| `fpga_bmc_firmware_zip` | `""` | Local path to BMC firmware zip |
| `fpga_bmc_firmware_version` | `""` | Approved BMC firmware version |
| `fpga_bittware_user` | `""` | Account that owns Bittware tooling |
| `fpga_update_grub` | `false` | Apply GRUB cmdline + grub-mkconfig + reboot |
| `fpga_update_bittware_sdk` | `false` | Install/refresh SDK deb |
| `fpga_update_bmc` | `false` | Program BMC firmware (always requires `--tags firmware`) |
| `users_setup_venvs` | `true` | Provision `~user/.bw_venv` for every bittware-group member |
| `fpga_reboot_on_change` | `true` | Reboot at end of play if GRUB/SDK/BMC changed |

## Tags

| Tag | Tasks |
|---|---|
| `fpga` | All of this role |
| `install` | apt + SDK install + venv create |
| `config` | udev + GRUB + venv ownership |
| `hardware` | udev, GRUB, reboot, BMC |
| `destructive` | GRUB, SDK, BMC, reboot |
| `firmware` | BMC firmware |
| `never` | BMC firmware (opt-in only) |

Tags: `fpga`, `install`, `config`, `hardware`, `firmware`, `destructive`, `never`.
