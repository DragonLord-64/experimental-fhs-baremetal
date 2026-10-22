# Provisioning Architecture

![Provisioning Environment Diagram](mid-cbf-provisioning-environement.excalidraw.png)

## Strategy

The provisioning workflow is divided into three distinct stages:
1. **Netbox:** Used for DCIM (Data Center Infrastructure Management).
2. **Openstack:** Used to image a server to a known baseline state.
3. **Ansible:** Used to deploy custom configurations on the server.

### Definitions

| Component | Description |
| :--- | :--- |
| **Netbox** | The source of truth containing all hardware details and the desired provisioning state. |
| **Inventory** | Dynamically created from Netbox. This step converts Netbox data into a format Ansible and Bifrost can understand. **Note:** Netbox is the source of truth; files must be updated from Netbox before provisioning. *Development Note:* Inventory files can be saved/CM'd to maintain multiple different provisioned configurations. |
| **BAR** | SKA's artifact repository. **ALL EXTERNAL DEPENDENCIES** (repos, tarballs, binaries, applications, bitstreams, etc.) are contained here. Ansible pulls directly from BAR to FHS servers (no intermediate copy). BAR element names must sync with Netbox; if an artifact is missing, Ansible will fail loudly by design. |
| **Ansible** | The application used to provision the servers. |
| **Openstack/Ironic/Bifrost** | The application suite used to image the servers. |


### Deployment Interface & Exporting
  
The key link between deployment and provisioning is the **server role name**. All other attributes—such as taint/label, IP address, and hostname—are derived from this role name (e.g., `VCC-UNIT1:FHS1`). These role names and the logic used to derive taints, labels, and IPs must be maintained identically between the two repositories.

Once the environment is fully deployed, a provisioning export must be generated. This file maps **Roles to IPs**, which is required to:
* Deploy pods to the correct FHS nodes.
* Establish connectivity to the 400G Switches.
---

## Process Flow

1. **Inventory Creation** (Netbox)
2. **Image Building** (Bifrost/DiskimageBuilder)
3. **Server Enrollment** (Openstack/Bifrost)
4. **Server Imaging** (Openstack/Bifrost)
5. **Dependencies & Artifacts** (Gitlab, BAR, Platform)
6. **FHS Provisioning** (Ansible + Netbox)
7. **K8s Cluster Join**

---

## 1. Inventory Creation

Netbox serves as the single source of truth for all hardware and configuration data required for provisioning.

![Netbox Diagram](netbox.excalidraw.png)

### Mid.CBF Inventory File
This file is generated dynamically from Netbox and is used directly by Ansible and Bifrost. The Netbox API will be used to create the inventory at run time.

**Note: Netbox is the absolute source of truth.**

```yaml
---
sys1353:
  uuid: "00000000-0000-0000-0000-000000001353"
  name: sys1353
  boot_interface: ipxe
  driver: "redfish"
  driver_info:
    redfish_address: "https://192.168.8.30"
    redfish_username: "admin"
    redfish_password: "b1ttwar3"
    redfish_verify_ca: false
  root_device:
    size: "> 900"
  nics:
    - mac: a8:a1:59:f8:7d:a5   
  ipv4_address: 192.168.8.31
  ipv4_subnet_mask: 255.255.0.0
  driver_interfaces:
    raid: "none"
  properties:
    cpu_arch: x86_64
    ram: "524288"
    disk_size: "931"
    cpus: "64"
    capabilities: "boot_mode:uefi"
    root_device:
      size: "> 900"
  instance_info:
    image_source: "http://192.168.1.6:8080/tb_jammy_2025_12_03.qcow2"
    image_checksum: "fbf195b96f1b6da1a372fbd5560b137b"
    capabilities:
      boot_mode: uefi
```

---

## 2. Building an Image

The Bifrost environment utilizes **DiskimageBuilder** to create base images.

![Image Building Diagram](image-building.excalidraw.png)

### Image YAML Configuration
This defines the base image and filename. It references a block device configuration.

```yaml
---
- imagename: tb_jammy_2025_12_03.qcow2
  elements: [base, ubuntu, vm, growroot, block-device-efi-lvm, cloud-init-datasources]
  image-size: 925
  environment:
    DISTRO_NAME: ubuntu
    DIB_RELEASE: jammy
    DIB_CLOUD_INIT_DATASOURCES: "Ec2, ConfigDrive, OpenStack"
    DIB_BLOCK_DEVICE_CONFIG: file:///<path to block device file> # Three slashes required
```

### Block Device YAML Configuration
This section sets up the partitions on the hard drive using **LVM (Logical Volume Manager)**.

```yaml
- local_loop:
    name: image0
- partitioning:
    base: image0
    label: gpt
    partitions:
      - name: ESP
        type: EF00
        size: 512MiB
        mkfs:
          type: vfat
          mount:
            mount_point: /boot/efi
            fstab:
              options: "defaults"
              fsck-passno: 2
      - name: BSP
        type: 'EF02'
        size: 8MiB
      - name: root
        type: '8300' 
        flags: [boot]  
        size: 100%
- lvm:
    name: lvm
    base: [ root ]
    pvs:
      - name: pv
        base: root
        options: ["--force"]
    vgs:
      - name: vg
        base: ["pv"]
        options: ["--force"]
    lvs:
      - name: lv_root
        base: vg
        extents: 22%VG
      - name: lv_tmp
        base: vg
        extents: 4%VG
      - name: lv_var
        base: vg
        extents: 25%VG
      - name: lv_log
        base: vg
        extents: 16%VG
      - name: lv_audit
        base: vg
        extents: 5%VG
      - name: lv_home
        base: vg
        extents: 18%VG
- mkfs:
    name: fs_root
    base: lv_root
    type: xfs
    label: "img-rootfs"
    mount:
      mount_point: /
      fstab:
        options: "rw,relatime"
        fsck-passno: 1
# ... (subsequent mkfs entries follow same logic for /tmp, /var, /var/log, /var/log/audit, /home)
```

### Notes on Cloud-init
**Cloud-init** is a service that runs early in the Ubuntu startup process. It is responsible for configuring the initial IP address and user access provided during the image deployment stage.

---

## 3. Enrolling the Server

This is a Bifrost step to add servers to the Bifrost Ironic service in preparation for Openstack deployment.

```bash
# Set the inventory source
export BIFROST_INVENTORY_SOURCE=<path_to_mid-cbf-inventory.yml> 

# Enroll servers (use -vvvv for maximum logging verbosity)
ansible-playbook -vvvv -i inventory/bifrost_inventory.py enroll-dynamic.yaml 

# Note: bifrost_inventory.py is a helper script used by Bifrost to format the data correctly.
```

---

## 4. Server Imaging

Bifrost uses **PXE booting** (HTTP Boot) to prepare the server.

![Image Deployment Diagram](image-deployment.excalidraw.png)

### The PXE Process
1. The FHS BIOS is instructed to search the network port for an image.
2. A **DHCP server** provides a temporary IP.
3. An **HTTP server** provides a **ramdisk image** (an OS stored entirely in RAM).
4. Once booted, an Ansible script wipes the existing hard drives.
5. The server is then configured to download and boot the target built image (from Step 2) provided via HTTP.

### Deployment Command
```bash
export BIFROST_INVENTORY_SOURCE=<inventory_file_path>.yml 
ansible-playbook -vvvv -i inventory/bifrost_inventory.py deploy-dynamic.yaml
```

### Initial Access
After the initial Ubuntu boot, **Cloud-init** configures the permanent IP and user credentials, allowing Ansible and system maintainers to access the server.

---

## 5. FHS Configuration via Ansible

Once the base image is deployed, Ansible installs and configures the following:
* Network stack
* Users and Access Control
* Drivers and Packages
* Mid.CBF Monitoring Services (Prometheus)
* DPDK
* Kubernetes
* BIST

![Ansible FHS Configuration Diagram](ansible-fhs-configuration.excalidraw.png)

Ansible allows for simultaneous configuration of multiple servers. **Variables** are utilized to provide unique configurations for each FHS, while **Ansible Roles** are used to ensure the process is modular and organized.

---

## 6. Joining K8s Cluster

Ansible automates the final process of joining the newly provisioned nodes to the existing Kubernetes cluster.

After the server has joined the cluster, taints and toleration may need to be applied by another playbook.

---
