# bifrost-infra — VM-based test cycle setup

This document is a fast-path recipe for getting `test-bifrost.yaml` (the upstream libvirt-VM-backed deploy validation playbook) to pass green on a fresh Ubuntu machine. Once this passes, the deploy cycle works against a fake bare-metal node (libvirt VM + sushy-emulator Redfish + DHCP/TFTP/IPA/cirros), which is the same machinery the production flow uses against real hardware.

For overall architecture, real-hardware provisioning, and DIB image-build details, see [`README.md`](README.md). This file only covers the test cycle.

---

## 1. TL;DR

**Retesting an existing setup:** `./bifrost-infra/run-test.sh` runs the full cleanup + create-vm + deploy cycle and exits 0 iff the controller play recap shows `failed=0` and the node ends up `active+power-on`. Use this for repeat runs once the container has been built.

**First-time setup**, on a fresh box where the host is already prepared (KVM, Docker, qemu, libvirt installed):

```bash
git clone <repo-url> ska-mid-cbf-fhs-baremetal && cd ska-mid-cbf-fhs-baremetal
touch .vault_pass
sudo mkdir -p /var/lib/ironic
sudo docker compose -f bifrost-infra/docker-compose.yml up -d --build

sudo docker exec bifrost_deploy bash -c '
  cd /bifrost/playbooks
  env -u ANSIBLE_VAULT_PASSWORD_FILE \
    ansible-playbook -i inventory/localhost test-bifrost-create-vm.yaml \
      -e test_vm_domain_type=kvm \
      -e test_vm_node_driver=redfish
  python3 -c "
import json
p = \"/tmp/baremetal.json\"
d = json.load(open(p))
for v in d.values(): v[\"driver_info\"][\"redfish_auth_type\"] = \"basic\"
json.dump(d, open(p, \"w\"), indent=2)
"
  export BIFROST_INVENTORY_SOURCE=/tmp/baremetal.json
  env -u ANSIBLE_VAULT_PASSWORD_FILE \
    ansible-playbook -i inventory/bifrost_inventory.py -i inventory/target test-bifrost.yaml \
      -e download_custom_deploy_image=true \
      -e testing_user=cirros \
      -e download_ipa=true \
      -e create_ipa_image=false \
      -e ipv4_nameserver=8.8.8.8
'
```

Success criterion: `127.0.0.1: failed=0` in the final PLAY RECAP. The `testvm1: failed=1` line from a `ssh-keygen -R` cleanup task is expected and harmless.

The rest of this document walks through each step and explains why it exists.

---


## 2. Install host packages

```bash
# Docker Engine (Ubuntu's docker.io works fine; the official apt repo is also OK)
sudo apt update
sudo apt install -y docker.io docker-compose-v2

# QEMU + libvirt userspace (the container has its own, but we need these on the
# host for one-shot diagnostics; they also pull in the right kvm group)
sudo apt install -y qemu-system-x86 libvirt-daemon-system

# Add yourself to the docker group OR remember to use `sudo docker` every time
sudo usermod -aG docker "$USER"
# log out / log back in for group change to take effect, or use sudo docker below
```

> **Note on package names:** on Ubuntu 26.04, `qemu-kvm` is a virtual package — the real one is `qemu-system-x86`. On 22.04/24.04 either name works.

---

## 3. Clone and configure

```bash
git clone <repo-url> ska-mid-cbf-fhs-baremetal
cd ska-mid-cbf-fhs-baremetal
touch .vault_pass
sudo mkdir -p /var/lib/ironic
```

That's it for per-machine setup. `docker-compose.yml` defaults every bind-mount path relative to the compose file, so a fresh clone works without further configuration on native Linux or WSL2 + Docker Engine.

The vault password file (`.vault_pass`) must exist for the read-only bind mount to work; the test cycle doesn't use vault, so an empty file is fine.

The ironic state directory (`/var/lib/ironic`) holds cached deployment images and master image hardlinks. We bind-mount the entire directory, not just `httpboot/`, because Ironic hard-links cached images between `master_images/` and `httpboot/` during deploy — if those sit on different filesystems, `link()` fails with `EXDEV`. Wired into `docker-compose.yml` already.

> **Docker Desktop on Windows only:** if the daemon sees a different filesystem from your shell (e.g. you cloned the repo under `/home/...` but the daemon mounts under `/mnt/wsl/...`), copy `bifrost-infra/.env.example` to `bifrost-infra/.env` and set absolute daemon-visible paths for `BIFROST_DIR`, `INVENTORY_DIR`, and `VAULT_PASS_FILE`. Native Linux and WSL2 + Docker Engine do not need this.

---

## 4. Build and start the container

```bash
sudo docker compose -f bifrost-infra/docker-compose.yml build
sudo docker compose -f bifrost-infra/docker-compose.yml up -d
sudo docker logs -f bifrost_deploy   # ^C once you see systemd settle (~10s)
```

The compose file is preconfigured with the WSL/cgroup-v2 settings needed for systemd-in-container to start:

- `cgroup: host`
- `tmpfs: [/run, /run/lock, /tmp]`
- `privileged: true`
- `network_mode: host`

If the container exits with code 255 immediately, you're missing one of those — verify nothing was lost when copying the compose file.

> `/dev/kvm` is exposed to the container automatically via the existing `/dev:/dev` bind + `privileged: true`. No extra device flag is needed.

---

## 5. OVMF firmware paths (handled by Dockerfile, nothing to do)

The kolla `bifrost-deploy:2026.1-ubuntu-noble` image ships only the 4 MiB OVMF firmware variants (`OVMF_VARS_4M.fd`, `OVMF_CODE_4M.fd`), but bifrost's libvirt XML logic can end up writing the legacy 2 MiB paths (`OVMF_VARS.fd`, `OVMF_CODE.fd`) into the domain XML — which then fails at VM start because those files don't exist.

The `Dockerfile` bakes in two `RUN ln -sf` symlinks that point the legacy names at the 4M variants, so either resolution works. Verify with:

```bash
sudo docker exec bifrost_deploy ls -la /usr/share/OVMF/OVMF_VARS.fd /usr/share/OVMF/OVMF_CODE.fd
```

Both should appear as symlinks to the `_4M.fd` files. If they're missing, your image was built from an older Dockerfile — rebuild with `sudo docker compose -f bifrost-infra/docker-compose.yml build --no-cache`.

---

## 6. Create the test VM (libvirt + sushy-emulator)

```bash
sudo docker exec bifrost_deploy bash -c '
  cd /bifrost/playbooks
  env -u ANSIBLE_VAULT_PASSWORD_FILE \
    ansible-playbook -i inventory/localhost test-bifrost-create-vm.yaml \
      -e test_vm_domain_type=kvm \
      -e test_vm_node_driver=redfish
'
```

What each extra var does:

| Var | Why |
|---|---|
| `test_vm_domain_type=kvm` | Overrides the role default of `qemu` (TCG). Requires nested virtualization to be enabled on the host. |
| `test_vm_node_driver=redfish` | The IPMI driver path uses `vbmcd`, which doesn't implement `Set System Boot Options` (`raw 0x00 0x08 0x05`). Switching to Redfish/sushy-emulator avoids that gap. |

This step writes `/tmp/baremetal.json` (inside the container) describing the just-created VM.

---

## 7. Patch the generated `baremetal.json` for sushy-emulator auth

sushy-emulator (the Redfish mock that backs the VM) doesn't implement `/redfish/v1/SessionService`, so Ironic's default session-based auth fails with 401. Force basic auth:

```bash
sudo docker exec bifrost_deploy python3 -c '
import json
p = "/tmp/baremetal.json"
d = json.load(open(p))
for v in d.values():
    v["driver_info"]["redfish_auth_type"] = "basic"
json.dump(d, open(p, "w"), indent=2)
'
```

---

## 8. Run the test cycle

```bash
sudo docker exec bifrost_deploy bash -c '
  cd /bifrost/playbooks
  export BIFROST_INVENTORY_SOURCE=/tmp/baremetal.json
  env -u ANSIBLE_VAULT_PASSWORD_FILE \
    ansible-playbook -i inventory/bifrost_inventory.py -i inventory/target test-bifrost.yaml \
      -e download_custom_deploy_image=true \
      -e testing_user=cirros \
      -e download_ipa=true \
      -e create_ipa_image=false \
      -e ipv4_nameserver=8.8.8.8
'
```

What each extra var does:

| Var | Why |
|---|---|
| `download_custom_deploy_image=true` | Pull a prebuilt cirros image instead of building one with DIB (DIB takes 30+ min). |
| `testing_user=cirros` | The SSH user for post-deploy validation. |
| `download_ipa=true` + `create_ipa_image=false` | Use the upstream-prebuilt Ironic Python Agent ramdisk; do not DIB-build it. |
| `ipv4_nameserver=8.8.8.8` | Required by the configdrive template (`ipv4_nameserver is string` chokes on undefined). |

The run takes 5–15 minutes on KVM — most of that is image downloads on the first run; subsequent runs are mostly cached. Watch with:

```bash
sudo docker exec bifrost_deploy tail -f /tmp/test-bifrost.log
```

or, if running the command above directly without redirection, just read the streaming output.

---

## 9. Verifying success

```bash
sudo docker exec bifrost_deploy baremetal node list
```

Expected:

```
| testvm1 | … | power on | active | False |
```

`provision_state=active` + `power_state=power on` means: Ironic enrolled the node, inspected it, deployed the image, rebooted into the deployed OS, and is happy.

The PLAY RECAP should show `127.0.0.1: failed=0`. You may see `testvm1: failed=1` — this is a final `ssh-keygen -R` cleanup task that fails with `rc=2` because there's no stale known_hosts entry to remove. Harmless.

---

## 10. Cleanup between runs

If you want to re-run cleanly (recommended any time you change one of the `-e` vars or hit a real failure):

```bash
sudo docker exec bifrost_deploy bash -c '
  # tear down the VM
  virsh destroy testvm1 2>/dev/null || true
  virsh undefine --nvram testvm1 2>/dev/null || true
  rm -f /var/lib/libvirt/qemu/nvram/testvm1_VARS.fd /var/lib/libvirt/nvram-testvm1.fd

  # delete the ironic node
  for n in $(baremetal node list -f value -c UUID); do
    baremetal node delete "$n"
  done
'
```

Then jump back to §6.

To nuke everything including the container:

```bash
sudo docker compose -f bifrost-infra/docker-compose.yml down -v
sudo rm -rf /var/lib/ironic   # WARNING: destroys cached images, ironic DB is in the container's overlay so it goes with `down`
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Container exits with code 255 immediately | cgroup-v2 systemd-in-container missing tmpfs/cgroup settings | Verify `cgroup: host` and `tmpfs: [/run, /run/lock, /tmp]` in `docker-compose.yml` |
| `FixedEndpointPlugin.__init__() got an unexpected keyword argument 'username'` | Ironic CLI sees `OS_CLOUD=bifrost` from container ENV but also `OS_AUTH_TYPE=none` from noauth-mode tasks | The `bifrost_venv_env: { OS_CLOUD: "" }` overrides in `inventory/group_vars/{localhost,target}` handle this — verify they're present |
| `set: Illegal option -o pipefail` during OCI registry upload | Upstream task uses bashisms but Ansible defaults to `/bin/sh` (dash) | `enable_oci_registry_upload: false` in `inventory/group_vars/target` (already set) |
| `Network is already in use by interface virbr0` | Stale libvirt default network from a previous run | `sudo docker exec bifrost_deploy virsh net-destroy default; virsh net-undefine default` |
| `Network interface virbr0 is not known to Ansible` (running `install.yaml` standalone) | `virbr0` doesn't exist until `bifrost-create-vm-nodes` creates it | Don't run `install.yaml` standalone for the test cycle — `test-bifrost.yaml` imports it after the VM is created |
| `ipv4_nameserver is undefined` at configdrive generation | configdrive template uses `ipv4_nameserver is string` which throws on undefined | Pass `-e ipv4_nameserver=8.8.8.8` (already in §8 command) |
| `[Errno 18] Invalid cross-device link` during deploy | `master_images` and `httpboot` are on different filesystems | Use the existing `/var/lib/ironic:/var/lib/ironic` mount in `docker-compose.yml` (don't narrow it to `httpboot` only) |
| `IPMI call failed: raw 0x00 0x08 0x05` | vbmcd doesn't implement `Set System Boot Options` | Use the redfish driver: `-e test_vm_node_driver=redfish` (§6) |
| Redfish 401 "Authorization required" at SessionService | sushy-emulator doesn't implement `/redfish/v1/SessionService` | Patch `redfish_auth_type=basic` into `/tmp/baremetal.json` (§7) |
| `Failed to open file '/usr/share/OVMF/OVMF_VARS.fd'` | Only 4M variants ship in the kolla image; XML references 2M path | Should be fixed automatically by the Dockerfile OVMF symlinks. If you see this, the image was built without the symlinks — rebuild with `--no-cache` (see §5) |
| `unsupported configuration: Emulator '...' does not support virt type 'kvm'` | Container's libvirt started before KVM was available, OR nested virt isn't actually enabled | Verify on the host with `grep -oE '(vmx\|svm)' /proc/cpuinfo`. If the flag is there but libvirt still rejects KVM, restart the container: `sudo docker restart bifrost_deploy` |
| `Could not access KVM kernel module: No such device` from qemu | `/dev/kvm` exists but kernel doesn't expose virt extensions to userspace | Host nested virt is not actually enabled. On WSL2, set `[wsl2] nestedVirtualization=true` in `%UserProfile%\.wslconfig`, then `wsl --shutdown` and reopen. On native Ubuntu, enable virtualization in BIOS |
