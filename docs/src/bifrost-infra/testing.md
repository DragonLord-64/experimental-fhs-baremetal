# Testing Guide

The `bifrost-infra/` container uses host networking and privilege. Review the target network before running it. Bifrost playbooks are supplied by the image under `/opt/bifrost/playbooks`.


This procedure uses the image-provided Bifrost libvirt tests. Review isolation and image dependencies before running it.

> [!WARNING]
> **ENVIRONMENT LIMITATION:** This test suite is intended for local development. It is **not** fully functional for all hardware types or complex network topologies. Use with caution.

## Overview

The test suite uses a "Fake Baremetal" approach. It creates a virtual machine that mimics a physical server with a BMC (Baseboard Management Controller).

| Playbook | Purpose |
| :--- | :--- |
| `test-bifrost-create-vm.yaml` | Creates a libvirt VM with a virtual BMC and writes its details to `/tmp/baremetal.json`. |
| `test-bifrost.yaml` | Runs the full cycle: **Install $\rightarrow$ Enroll $\rightarrow$ Deploy $\rightarrow$ SSH Verify $\rightarrow$ Unprovision**. |

**Note:** To ensure speed, the test suite uses [Cirros](https://github.com/cirros-dev/cirros) (a tiny ~20 MB image) instead of the heavy FHS DIB image.

## Prerequisites

To run these tests, the Docker container must have access to the host's virtualization capabilities:

1.  **Host KVM:** `/dev/kvm` must be present and accessible on the host machine.
2.  **Container Dependencies:** The `Dockerfile` must include `libvirt-daemon-system`, `libvirt-clients`, `python3-libvirt`, and `virtinst`.
3.  **Network (unverified here):** The image test suite is intended to switch the Bifrost network from the physical `eno2` to the virtual `virbr0` to avoid interfering with your real network.

---

## Running the Tests

All commands must be executed from **inside the Docker container**.

### 1. Prepare the Environment
If you haven't already, ensure the Bifrost services are running.
```bash
sudo docker exec -it bifrost_deploy bash
cd /bifrost/playbooks

# Ensure services are installed
ansible-playbook -i inventory/target install.yaml
```

### 2. Create the Virtual Baremetal Node
This step generates the "fake" hardware profile that the dynamic inventory will use.
```bash
# This creates the VM and writes node details to /tmp/baremetal.json
ansible-playbook -vvvv -i inventory/localhost test-bifrost-create-vm.yaml
```

### 3. Execute the Full Test Cycle
We pass specific extra variables (`-e`) to override the default FHS settings and use the Cirros image.

```bash
# 1. Point the dynamic inventory to the generated JSON file
export BIFROST_INVENTORY_SOURCE=/tmp/baremetal.json

# 2. Run the full test cycle
ansible-playbook -vvvv -i inventory/bifrost_inventory.py -i inventory/target test-bifrost.yaml \
  -e download_custom_deploy_image=true \
  -e testing_user=cirros \
  -e download_ipa=true \
  -e create_ipa_image=false
```

---

## Test Lifecycle Breakdown

The following table describes what happens during the `test-bifrost.yaml` execution:

| Phase | Playbook / Task | Description |
| :--- | :--- | :--- |
| **Install** | `install.yaml` | Ensures Ironic, dnsmasq, and HTTP services are running. |
| **Enroll** | `enroll-dynamic.yaml` | Registers the libvirt VM as a node in the Ironic database. |
| **Deploy** | `deploy-dynamic.yaml` | The VM boots via iPXE and receives the Cirros image. |
| **Verify** | `bifrost-test-vm` | The runner SSHes into the VM as `cirros` to confirm OS readiness. |
| **Cleanup** | `ironic-delete-dynamic` | The VM is unprovisioned, the disk is wiped, and the node is removed. |

## Troubleshooting Tests

* **KVM Errors:** If you see errors regarding `kvm` or `acceleration`, ensure the Docker container was started with `--privileged` and that `/dev/kvm` is passed through.
* **Network Failures:** If the VM cannot reach the DHCP server, verify that the `testing: true` flag is active, which switches the binding to `virbr0`.
* **SSH Failures:** If the "Verify" phase fails, check if the `testing_user` variable matches the default user of the image being used (e.g., `cirros`).
