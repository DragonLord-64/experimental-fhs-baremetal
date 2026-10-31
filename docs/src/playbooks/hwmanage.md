# Hardware management

Run `hwmanage` inside the provisioning container, from `/provision`. It wraps
selected Ironic/Bifrost operations and Ansible playbooks. Native applications and
YAML inventories remain available independently.

```bash
cd /provision
scripts/hwmanage --help
scripts/hwmanage node --help
scripts/hwmanage provision --help
```

Use `scripts/hwmanage` in these commands, or place a symlink named `hwmanage` on
your executable search path. Every command and subcommand supports `--help`.

## Select inventory and targets

`-i netbox` reads approved NetBox configuration. `-i ironic` reads Ironic
registrations and saved inspection. `-i /path/inventory.yml` selects a local YAML
inventory. A service failure never silently switches inventory sources.

Every action requires `--limit PATTERN` or `--all`. Use the reviewed NetBox device
name for NetBox input, an Ironic name/UUID for Ironic input, or a YAML inventory
host key. Device roles are inventory groups, not hostnames. Names can change;
the imported Ironic UUID identifies the same registration.

```bash
scripts/hwmanage node list -i ironic
scripts/hwmanage inventory import -i ironic --all
```

Initial import needs no installed OS or SSH. It creates the minimal NetBox device,
verified serial, BMC addressing and provisioning interface/MAC. Review the device
in NetBox before deploying: assign its intended Linux primary IP, role/tags and
deployment configuration. The temporary inspection DHCP address is not a Linux
address assignment.

## Prepare import settings

Copy the template to the provisioning host's private resource directory:

```bash
cp bifrost-infra/templates/hwmanage-import.yml /provision/files.d/hwmanage-import.yml
```

Edit `/provision/files.d/hwmanage-import.yml` with existing NetBox object IDs and
reviewed motherboard interface names from inspection:

```yaml
site: 1
role: 1
device_type: 1
system_fru_id: '0'
onboard_interfaces:
  - enp2s0f0
```

The numeric IDs above are examples, not automatic object selections. A boot MAC
must match exactly one inspected interface; `onboard_interfaces` qualifies that
interface after hardware review. The importer verifies FRU through controller-side
IPMI when the inspection does not establish FRU identity. The import playbook
installs `ipmitool` on the provisioning host, not the uninstalled target OS.
The controller therefore needs package-install privileges for the first run.

Copy `bifrost-infra/templates/hwmanage-bmc-secrets.yml` to
`/provision/files.d/credentials/redfish.yml`, supply the BMC login and encrypt it:

```bash
ansible-vault encrypt /provision/files.d/credentials/redfish.yml
```

The credential format is:

```yaml
redfish_credentials:
  defaults:
    redfish_username: REPLACE_USER
    redfish_password: REPLACE_PASSWORD
  devices: {}
```

Per-device overrides use the Ironic UUID or reviewed hostname under `devices`.
No BMC password belongs in a NetBox config context.

The direct import playbook installs the controller's `ipmitool` and invokes the
import service independently of the `hwmanage` command dispatcher:

```bash
ansible-playbook -i localhost, playbooks/netbox/ironic_import.yml \
  -e hwmanage_all=true

# Or select one exact Ironic name/UUID:
ansible-playbook -i localhost, playbooks/netbox/ironic_import.yml \
  -e hwmanage_limit=REPLACE_WITH_IRONIC_UUID
```

For read/validation without NetBox writes, add `--check`. The same private
platform, BMC and import settings files are used.

## Shared deployment settings

Copy the contents of
`bifrost-infra/templates/hwmanage-profile.yml` into a NetBox config context and
assign it to the intended device roles/tags. Replace the example network, image
URL, checksum and root disk with approved values. These are native Bifrost fields:

```yaml
driver: redfish
boot_interface: ipxe
driver_interfaces:
  raid: none
ipv4_subnet_mask: 255.255.255.0
ipv4_nameserver: 192.0.2.53
ipv4_gateway: 192.0.2.1
instance_info:
  image_source: http://192.0.2.10:8080/approved-image.qcow2
  image_checksum: REPLACE_WITH_VERIFIED_CHECKSUM
  capabilities:
    boot_mode: uefi
properties:
  root_device:
    name: /dev/disk/by-id/REPLACE_WITH_APPROVED_DISK
```

For direct Bifrost use, merge the same settings into its existing
`inventory/group_vars/baremetal` and apply node-specific overrides in the node
mapping. `bifrost-infra/templates/hwmanage-nodes.yml` shows the mapping format.
Keep installer DHCP/image-build/service configuration in Bifrost group vars;
it is separate from the node deployment profile.

## Individual node operations

NetBox is the default source except for `node list`, which defaults to Ironic.
Operations resolve the existing UUID rather than create a duplicate discovery.

```bash
scripts/hwmanage node show --limit SYS1412
scripts/hwmanage node enroll --limit SYS1412
scripts/hwmanage node sync --limit SYS1412
scripts/hwmanage node manage --limit SYS1412
scripts/hwmanage node inspect --limit SYS1412
scripts/hwmanage node clean --limit SYS1412
scripts/hwmanage node provide --limit SYS1412
scripts/hwmanage node deploy --limit SYS1412
```

`enroll` creates a missing registration without resetting an existing node's
state. `sync` updates approved fields without requesting a state transition.
`manage`, `inspect`, `provide`, `deploy` and `adopt` use native Ironic operations;
adoption is for an already installed system and is not a database-only import.

Manual cleaning defaults to partition/filesystem metadata removal. Supply native
clean steps as JSON, a JSON file or `-` for standard input:

```bash
scripts/hwmanage node clean --limit SYS1412 \
  --clean-steps '[{"interface":"deploy","step":"erase_devices_metadata"}]'
```

Individual actions support `--plan` to resolve/validate without applying the
operation. A plan can still read selected services or hardware identity.

## Provision an installed system

```bash
scripts/hwmanage provision -i netbox --limit SYS1412
scripts/hwmanage provision -i netbox --limit SYS1412 --tags manage_users
scripts/hwmanage provision -i netbox --limit SYS1412 --tags inventory
```

`provision` runs the repository's provisioning playbook. Role tags pass through
to Ansible; use the tags in [site.yml](site.yml.md). Inventory-only collection
requires its tools, including the BittWare SDK, to be installed already. Use full
provisioning before collecting a freshly deployed server.

Individual playbook commands accept `-e KEY=VALUE` and protected extra-variable
files. Target identity and scope cannot be overridden through extra variables:

```bash
scripts/hwmanage provision -i /provision/files.d/hosts.yml --limit SYS1412 \
  -e @/provision/files.d/overrides.yml
```

## Fixed runbooks

```bash
scripts/hwmanage run inspect-host -i ironic --limit <IRONIC_UUID>
scripts/hwmanage run provide-node -i netbox --limit SYS1412
scripts/hwmanage run full-provision -i netbox --limit SYS1412
```

`inspect-host` prepares and inspects a node. `provide-node` metadata-cleans and
deploys a fresh OS, then waits for SSH. `full-provision` also runs complete
provisioning before detailed inventory. The reimage workflows erase device
metadata and overwrite the selected OS disk; they reject active nodes.

Runbooks accept only inventory and target selection. For custom cleaning or
selective provisioning, use individual operations instead. Metadata cleaning is
not secure disk erasure. Automatic cleaning stays disabled.

## Export and run native commands

Export reviewed configuration before depending on it offline. The destination
must be a new directory:

```bash
scripts/hwmanage inventory export -i netbox --limit SYS1412 \
  --output-dir /provision/files.d/manual
```

The private directory contains `nodes.yml` (native Bifrost mapping),
`inventory.yml` (native Ansible inventory), and `group_vars/baremetal`. Deployment
settings are embedded in the nodes. Credentials stay separate; the snapshot does
not silently refresh when NetBox changes.

Use the native Ansible inventory directly if the wrapper or NetBox is unavailable:

```bash
ansible-playbook -i /provision/files.d/manual/inventory.yml \
  playbooks/provision.yml --limit SYS1412
ansible-playbook -i /provision/files.d/manual/inventory.yml \
  playbooks/site.yml --limit SYS1412 --tags inventory
```

For direct Bifrost deployment, first prepare the selected node's lifecycle with
the native `baremetal` CLI. Supply your protected BMC credentials through the
normal Bifrost vars/inventory mechanism, then run:

```bash
export BIFROST_INVENTORY_SOURCE=/provision/files.d/manual/nodes.yml
cd /bifrost/playbooks
ansible-playbook -i inventory/bifrost_inventory.py -i inventory/localhost \
  deploy-dynamic.yaml --limit 'localhost,SYS1412' \
  -e @/provision/files.d/manual/group_vars/baremetal \
  -e wait_for_node_deploy=true
```

This writes an OS image. It is not a replacement for required enrollment,
management, explicit cleaning and availability transitions. Native `baremetal`
remains available for lifecycle operations outside this wrapper.

## Check services and connectivity

Run system checks on the provisioning host. Set the URL to a real served boot
asset, not just the web server root:

```bash
export HWMANAGE_BOOT_URL=http://192.168.1.7:8080/ipa.kernel
scripts/hwmanage check systems
scripts/hwmanage check hosts -i netbox --limit SYS1412
scripts/hwmanage check hosts -i netbox --all
```

System checks read Ironic API/readiness, effective automatic-cleaning policy,
dnsmasq syntax, application-service status, NetBox access and the boot asset.
They report failures and do not repair services. Host checks use Ansible Linux
or Nexus management connectivity, rather than ICMP alone.

## Configure provisioning services

```bash
scripts/hwmanage config ironic --automated-clean false
scripts/hwmanage config dnsmasq add-host -i netbox --limit switch01
scripts/hwmanage config dnsmasq list-hosts
scripts/hwmanage config dnsmasq remove-host -i netbox --limit switch01
```

Explicit switch overrides use the boot-file path and boot-server address:

```bash
scripts/hwmanage config dnsmasq add-host -i netbox --limit switch01 \
  --mac 02:00:00:00:00:02 --ip 192.0.2.40 --group real-nexus-poap \
  --boot-server 192.0.2.10 --boot-file poap_script.py
```

NetBox defaults use the switch's `mgmt0` MAC, primary address and config-context
fields `dhcp_group`, `poap_server` and `poap_boot_file`. Explicit MAC/IP overrides
require one target. Review the existing switch POAP serial/address mapping too;
DHCP reservation alone does not configure the switch OS. `--image` is an alias
for `--boot-file`; it identifies the boot script, not a switch software image.

Ironic configuration edits disable automatic cleaning and validate the staged
configuration. dnsmasq edits use the dedicated `/etc/dnsmasq.d/hwmanage.conf`
include and validate syntax. Neither command restarts services automatically;
follow its activation message. Existing Cisco POAP files are retained. A switch
boot file is the POAP script, not its NX-OS image.

## Local settings

The existing platform files are read on the Ansible/provisioning host:

```text
/provision/files.d/platform-endpoints.yml
/provision/files.d/credentials/platform-secrets.yml
```

Keep the secrets file encrypted with Ansible Vault using the configured password
file. `FHS_PLATFORM_ENDPOINTS_FILE` and `FHS_PLATFORM_SECRETS_FILE` select other
paths. `HWMANAGE_BMC_SECRETS` selects protected BMC credentials; the default is
`/provision/files.d/credentials/redfish.yml`.

The empty `inventory/dev_env/hwmanage-vars.yml` source loads the adjacent
`group_vars`/`host_vars` alongside generated hosts. It does not load the NetBox
inventory plugin. Set `HWMANAGE_SITE_INVENTORY` to another equivalent static
inventory source if your site variables live elsewhere. Exported snapshots
materialize those variables for direct offline use.

`HWMANAGE_IRONIC_CONFIG` selects the effective Ironic config file(s), separated
by `:` in service order. `HWMANAGE_DNSMASQ_CONFIG` selects dnsmasq's main config;
`HWMANAGE_DNSMASQ_INCLUDE` selects its dedicated `hwmanage.conf` include.
`HWMANAGE_SERVICES` selects space-separated application service names for checks.

Lifecycle waits default to 1,800 seconds, allowing for slow firmware boots.
`HWMANAGE_TIMEOUT` adjusts lifecycle waits; `HWMANAGE_ANSIBLE_TIMEOUT` adjusts
provisioning execution. A timeout stops the workflow: inspect native application
state before repeating a cleaning or deployment operation.
