

The following is the source deployment procedure, not a completed dragonvm provisioning test. The tracked `bifrost-infra/` container definition uses host networking and privilege; do not use it as a disposable lab fixture. Bifrost playbooks come from the image under `/opt/bifrost/playbooks`, not this repository. The separate [restricted lab smoke](https://github.com/DragonLord-64/experimental-fhs-baremetal/blob/development/ops/provisioning/README.md) passed only the empty Ironic API and KVM capability checks; full guest provisioning and physical hardware behavior remain untested.

# Recovery Guide

This guide provides instructions for recovering your environment if the Docker container is destroyed or the Ironic database is lost.

## Scenario: Container Loss / Database Reset
If the Docker container is deleted, the Ironic database (which stores the state and registration of all enrolled nodes) is lost. While the physical servers are still running, Bifrost no longer "knows" they belong to it.

**Goal:** Re-add the existing servers to Ironic without erasing their disks or re-deploying the OS.

### Step 1: Rebuild the Environment
Follow the **[Quickstart Guide](./QUICKSTART.md)** to rebuild the container and start the services.

### Step 2: Disable Automatic Cleaning
By default, Ironic attempts to wipe disks when a node is enrolled. To prevent data loss on existing servers, you **must** disable this before proceeding.

1.  **Access the container:**
    ```bash
    docker exec -it bifrost_deploy bash
    ```

2.  **Modify the Ironic configuration:**
    ```bash
    nano /etc/ironic/ironic.conf
    ```
    Find the following line and ensure it is set to `false`:
    ```ini
    automated_cleaning = false
    ```

3.  **Restart the Ironic service:**
    ```bash
    systemctl restart ironic
    ```
    *Exit the container once complete.*

### Step 3: Re-Enroll the Nodes
Now, re-register the hardware. Ironic will see these as "new" nodes, but because `automated_cleaning` is disabled, it will not wipe them.

```bash
# 1. Point to your existing hardware definition file
export BIFROST_INVENTORY_SOURCE=/bifrost/playbooks/inventory/your_nodes.yaml

# 2. Run the enrollment playbook
ansible-playbook -i inventory/bifrost_inventory.py -i inventory/localhost enroll-dynamic.yaml
```

### Step 4: Adopt the Nodes
After enrollment, the nodes are in the database but are not yet "active" in the eyes of the controller. You must manually move them from a `provisioning` or `available` state to `active`.

1.  **List the nodes to confirm they are present:**
    ```bash
    baremetal node list
    ```

2.  **Manage and Adopt each node:**
    Run these commands for every node in your inventory:
    ```bash
    # Tell Ironic to take control of the node
    baremetal node manage <node_name>

    # Set the node to an active state
    baremetal node adopt <node_name>
    ```

### Verification
Once finished, run `baremetal node list` again. All nodes should now show a status of **`active`**. Your environment is now recovered and ready for future deployments.