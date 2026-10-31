# Operations Guide

The `bifrost-infra/` container uses host networking and privilege. Review the target network before running it. Bifrost playbooks are supplied by the image under `/opt/bifrost/playbooks`.


*Complete [setup](setup.md) before starting the processes defined in this section.*

This guide covers the operation of the `bifrost-infra` environment, including inventory configuration, node provisioning, and deployment.
This environment uses openstack Bifrost to manage FHS servers. 

For information on bifrost see: [bifrost-docs](https://docs.openstack.org/bifrost/latest/)



## 1. Installation and Inventory Management

Bifrost uses Ansible `group_vars` to manage global settings.

### Global Variables (`inventory/group_vars/`)

| Group | Purpose | Key Variables to Edit |
| :--- | :--- | :--- |
| **`localhost`** | Configures the Bifrost container. | `network_interface` (Host NIC), `file_url_port` (HTTP port). |
| **`baremetal`** | **Primary Config.** Sets defaults for all nodes. | `driver` (redfish/ipmi), `boot_interface`, `instance_info.image_source` (OS URL), `instance_info.image_checksum`. |
| **`target`** | Controls deployment-time behavior. | `cleaning` (Wipe disks), `enable_oci_registry_upload`. |

Set variables in the group that consumes them; inspect the imported Bifrost role defaults before overriding.

### Defining the deployment image

The OS image to be installed on the FHS servers must be defined in `baremetal`.
**Default configuration**
```yaml
deploy_image_filename: "deployment_image.qcow2"
deploy_image: "{{http_boot_folder}}/{{deploy_image_filename}}"
```
The image filename must match the name of the .qcow file which must reside within the httpboot folder (default location is `/var/lib/ironic/httpboot`).

See [Building an OS image](diskimage-builder.md) in this section for instruction on creating a custom OS image.

### Per-Node Configuration

FHSs are defined in a YAML file at `inventory/terabox1501b_inventory.yaml`

**Required fields per node:**
* `uuid`: Unique Ironic ID.
* `name`: Hostname.
* `nics.mac`: MAC address of the PXE-capable interface.
* `ipv4_address`: The IP assigned set through cloud-init (becomes the static IP of the server after imaging)
* `driver_info.redfish_address` (and associated credentials): BMC connectivity.
* `properties`: Hardware specifics (`cpu_arch`, `ram`, `disk_size`, etc.).

**Default inventory**
```yaml
sysXXXX:
  uuid: "00000000-0000-0000-0000-00000000<INSERT 4 number SN>"
  name: <INSERT HOST NAME>
  driver_info:
    redfish_address: "https://<INSERT IP ADDRESS OF BMC>"
    redfish_username: "<PROTECTED_VALUE>"
    redfish_password: "<PROTECTED_VALUE>"
    redfish_verify_ca: false
    deploy_kernel_append_params: "iommu=pt"
  root_device:
    size: "> 900"
  nics:
    - mac: <INSERT MAC OF NIC CONNECTED TO PROVISIONING NETWORK>
  ipv4_address: <INSERT DESIRED IP ADDRESS>
  properties:
    cpu_arch: x86_64
    ram: "128000"
    disk_size: "931"
    cpus: "32"
    capabilities: "boot_mode:uefi"
    root_device:
      size: "> 900"


```

**Note** You must place you

### Installing Bifrost

Once the container is running, you must run the installation playbook to set up bifrost, DNS, and HTTP services as well as build required images.
*Note: the ramdisk is built at this time*

#### Setting the Host Network interface

Bifrost install create a DHCP server (dnsmasq) and an ngninx http enpoint. There require a physical interface an IP. The interface name must be set in the local_host and target group vars (`ska-mid-cbf-fhs-baremetal/bifrost-infra/inventory/group_vars`).

```bash
# Example
network_interface: "eno2"
internal_ip: 192.168.1.7"
```
This interface usually need to be change **per host** as the name an IP will differ depending on the specific configuration of the host server.

The DHCP server must also be configured with an appropriate ip range **on the same subnet as the defined interface**.
This can also be defined in
`ska-mid-cbf-fhs-baremetal/bifrost-infra/inventory/group_vars/target`

```bash
# Example
dhcp_pool_start: "192.168.1.200"
dhcp_pool_end: "192.168.1.250"
```

*Its also possible to manually set this after install in /ect/dnsmasq.conf (remeber to restart the service after changing this file).*

#### Running the installation
Bifrsot provides an installation playbook to setup and configure the bifrost environment and supporting services (ngninx, dhcp, ironic)

```bash
ansible-playbook -i inventory/target install.yaml
```

The variables in /bifrost/playbooks/inventory define the bifrost installation. See the bifrost documentation for details:



---

### (Optional) Building an OS Image

The bifrost environment comes with diskimage-builder. This software can be used to create a custom image with a specified partition layout.

See [diskimage-builder.md](diskimage-builder.md) for details.


## 2. Deployment Workflow

To deploy hardware, you must follow a two-step process: **Enrollment** (register the hardware) and **Deployment** (install the OS).

### Step 1: Enrollment
Enrollment registers the physical hardware into the Ironic database.
The following steps occur automatically
- bifrost reboots the FHS through the BMC Redfish interface
- bifrost provides a DHCP and http server over the 192 network.
- the FHS (configured to PXE boot) searches for available DHCP server and discovers the bifrost DHCP and corresponding http server
- the FHS downloads the ramdisk from the http server and boots.
- the ramdisk contains the ironic python agent (ipa)
- the ipa pings bifrost over the network and begins node cleaning.
- the ipa wipes/cleans all harddrives.
- the ipa reports complete (or failed) to bifrost.
- the ipa maintains a heartbeat call with bifrost.

> [!CAUTION]
> **AUTOMATIC CLEANING:** By default, Ironic may attempt to clean (wipe) a node upon enrollment. Verify the `cleaning` variable in `group_vars/target` is set to `false` if you are enrolling nodes that already contain data.

To enroll nodes, you must point the environment variable `BIFROST_INVENTORY_SOURCE` to your hardware YAML file.

```bash
# 1. Set the source of your hardware definitions
export BIFROST_INVENTORY_SOURCE=/bifrost/playbooks/inventory/your_nodes.yaml

# 2. Run the enrollment playbook
# We use the dynamic inventory plugin to turn your YAML into an Ansible list
ansible-playbook -i inventory/bifrost_inventory.py -i inventory/localhost enroll-dynamic.yaml
```

**To enroll a specific subset of nodes:**
Use the `--limit` flag to avoid accidental mass-enrollments. 
*Note: Always include `localhost` in the limit to ensure Ansible can resolve local networking/interfaces.*

```bash
ansible-playbook -i inventory/bifrost_inventory.py -i inventory/localhost enroll-dynamic.yaml --limit "node01,node02,localhost"
```
*The --limit option works for the deployment step as well*

### Step 2: Deployment
Once enrolled, you can trigger the actual OS installation.
The following steps occur automatically
- bifrost powers on the server
  - FHS PXE boots to the ipa ramdisk
- bifrost contacts the ipa running on the node ramdisk and instructs it to download and install an specified image provided on the http server.
- the ipa installs the OS on an available harddrive and setup the correct partitions.
- the ipa reports success/failure
- bifrost reboots the server and trigger it to boot from harddisk.

**To deploy enrolled nodes:**
```bash
ansible-playbook -i inventory/bifrost_inventory.py -i inventory/localhost deploy-dynamic.yaml
```

---

## 3. Common Tasks

### Updating the OS Image
When a new FHS image version is released:
1. Update `instance_info.image_source` in `inventory/group_vars/baremetal`.
2. Update `instance_info.image_checksum` in `inventory/group_vars/baremetal` (use `md5sum <image>`).
3. Re-run the `redeploy-dynamic.yaml` playbook. This playbook cleans and reimages in one step.


### Troubleshooting Connectivity
If a node fails to boot:
1. **Check BMC:** Verify you can reach the `redfish_address` from the host.
2. **Check DHCP/TFTP:** Ensure the `network_interface` in `group_vars/localhost` matches the host NIC used for PXE.
3. **Check Logs:** View Ironic logs inside the container:
   ```bash
   docker exec -it bifrost_deploy journalctl -u ironic
   ```

## Connect to ipa ramdisk
If the node gets stuck in the cleaning phase (clean failed), it is possible to inspect and run commands directly from the ramdisk of the booted device.

First locate the ip address assigned by the bifrost DHCP server.

```bash
cat /var/lib/misc/dnsmasq.leases
```
Find the latest/active ip address.
ssh into the server using
**username**: `<PROVISIONED_USER>`
**password**: `<PROTECTED_PASSWORD>`

```bash
ssh username@<ip address>
```

*The username and password variables are set by the ansible variables*
  `DIB_DEV_USER_USERNAME`: "<PROVISIONED_USER>"
  `DIB_DEV_USER_PASSWORD`: "<PROTECTED_PASSWORD>"
in the `/bifrost/playbooks/inventory/group_vars/target` file. These values are baked into the ramdisk image which is built at bifrost install time (the `install.yaml` playbook).

The ramdisk image is a light weight linux environment which can be used to view and edit logs, harddrives, raid, and other server states.

## Deleting a Node from ironic
To delete a node enrolled in the ironic data base, follow the example below.

```bash
()[root@rmdskadevdu002 playbooks]# baremetal node list
+--------------------------------------+---------------+---------------+-------------+-----------------+-------------+
| uuid                                 | name          | instance_uuid | power_state | provision_state | maintenance |
+--------------------------------------+---------------+---------------+-------------+-----------------+-------------+
| 00000000-0000-0000-0000-000000001390 | rm2skafhsdu03 | None          | power on    | active          | False       |
| 00000000-0000-0000-0000-000000001354 | sys1354       | None          | power on    | clean wait      | False       |
+--------------------------------------+---------------+---------------+-------------+-----------------+-------------+
()[root@rmdskadevdu002 playbooks]# baremetal node maintenance set sys1354
()[root@rmdskadevdu002 playbooks]# baremetal node delete sys1354
Deleted node sys1354
()[root@rmdskadevdu002 playbooks]# baremetal node list
+--------------------------------------+---------------+---------------+-------------+-----------------+-------------+
| uuid                                 | name          | instance_uuid | power_state | provision_state | maintenance |
+--------------------------------------+---------------+---------------+-------------+-----------------+-------------+
| 00000000-0000-0000-0000-000000001390 | rm2skafhsdu03 | None          | power on    | active          | False       |
+--------------------------------------+---------------+---------------+-------------+-----------------+-------------+
()[root@rmdskadevdu002 playbooks]# 
```


## Patch the running container environment

Run inside `bifrost_deploy`. The script is mounted from the repository's
`scripts/` folder into `/provision/scripts/`.

```bash
# Read versions, dependency conflicts and OpenSSL/Ironic import failures.
python3 /provision/scripts/patch-bifrost-environment.py diagnose

# Update system CA certificates, pip and certifi; then repeat diagnostics.
python3 /provision/scripts/patch-bifrost-environment.py update
```

Diagnostics return nonzero for outdated pip/certifi, broken imports or dependency
conflicts. Update saves package versions under `/var/tmp/bifrost-environment-patches/`,
installs the hash-verified pip 26.2.2 bootstrap wheel and certifi >= 2026.10.19
through `https://pypi.org/simple`. It does not restart services or change Ironic
configuration, node records or databases. The version snapshot is a diagnostic
record, not a complete environment backup or automatic rollback.

For an OpenSSL/cryptography import failure, use the **local upper-constraints file
matching the installed OpenStack release**. Diagnostics list common candidate
locations. Do not substitute constraints from another release.

```bash
python3 /provision/scripts/patch-bifrost-environment.py repair-openssl \
  --constraints /path/to/release/upper-constraints.txt
```

This separately updates only pyOpenSSL/cryptography and dependencies selected by
pip under those constraints, then runs diagnostics. It may still fail if the
release pins are incompatible with the installed environment. Keep Ironic running
until its imports pass and any current inspection/deployment has finished. Restart
only the actual Ironic service afterward.

These commands patch the container's system CA package and Kolla environment,
not other virtualenvs, IPA ramdisks or deployment images. The Python runtime itself
also needs the distributor's security updates. See the
[Python security announcement](https://discuss.python.org/t/109576).

A fresh container image is the durable fix, but the current Compose file does
not explicitly persist the Ironic database or `/etc/ironic`. Before replacing a
container, back up its database, configuration and credentials; retain the mounted
SSH keys and `/var/lib/ironic` images. An image build alone does not update the
running container, and rebuilding the existing Dockerfile alone does not guarantee
updated Python trust bundles. This patch script does not build or replace it.
