# Hardware management

Run `hwmanage` inside the provisioning container, from `/provision`. It wraps
selected Ironic/Bifrost operations and Ansible playbooks. Native applications and
YAML inventories remain available independently.

```bash
cd /provision
scripts/install-hwmanage.sh
hwmanage --help
hwmanage node --help
hwmanage provision --help
```

Run the installer as root inside the provisioning container; no `sudo` or
container rebuild is needed. It links `/usr/local/bin/hwmanage` to this checkout,
at `/provision/scripts/hwmanage/hwmanage`, so source updates apply immediately. Repeat it after recreating the container.
It updates existing links from the previous application locations, and refuses
to overwrite a file or a link to another tool.

The application lives in the existing `scripts/` bind mount. Source updates are
visible immediately; no image rebuild, container recreation or file copy is needed.

For a user-owned directory, run `scripts/install-hwmanage.sh "$HOME/.local/bin"`
and add that directory to `PATH`. Keep running commands from `/provision` so
Ansible uses the repository configuration. Every command and subcommand supports
`--help`.

## Select inventory and targets

`-i netbox` reads approved NetBox configuration. `-i ironic` reads Ironic
registrations and saved inspection. `-i /path/inventory.yml` selects a local YAML
inventory. A service failure never silently switches inventory sources.

Every action requires `--limit PATTERN` or `--all`. Use the reviewed NetBox device
name for NetBox input, an Ironic name/UUID for Ironic input, or a YAML inventory
host key. Device roles are inventory groups, not hostnames. Names can change;
the imported Ironic UUID identifies the same registration.

```bash
hwmanage node list -i ironic
hwmanage inventory import -i ironic --all
```

Import continues after per-node inspection, identity or write failures. Each failed
UUID is reported; the command exits nonzero if any node failed. Successful writes
are retained. Duplicate observed serials/BMC addresses reject every involved node
before writes. A write failure can leave partial objects for that node; review
its diagnostic before retrying.

`node sync` updates Ironic registration settings and ports from the selected
inventory. It does not collect or refresh saved inspection inventory.

Initial import needs no installed OS or SSH. It creates the minimal NetBox device,
verified serial, BMC addressing and provisioning interface/MAC. Review the device
in NetBox before deploying: assign its intended Linux primary IP, role/tags and
deployment configuration. The temporary inspection DHCP address is not a Linux
address assignment.

## Prepare import settings

Edit the `import` section of `/provision/scripts/hwmanage/config.yml`:

```yaml
import:
  new_device_defaults:
    site: MDA
    role: FPGA HOST SERVER
    device_type: Terabox1501b
  system_fru_id: '0'
  provisioning_interface: null
```

Use existing NetBox names or slugs for site and device role, and the model name
or slug for device type. The values above are examples. Resolution is exact;
missing or ambiguous matches fail before writes for that node. Use a unique slug
when names/models repeat. Existing devices retain their site, role and device type.
These defaults are resolved only when creating a device; unrelated commands do
not query or validate their NetBox matches. Numeric IDs remain supported for
older configurations.
`system_fru_id` selects the IPMI FRU record for chassis identity, normally `'0'`.
The provisioning interface is the unique inspected boot-MAC match. Set a name
only to require that interface; missing, ambiguous or conflicting matches fail.
No `onboard_interfaces` declaration is needed.

The importer verifies identity through a controller-side IPMI FRU read.
The import playbook installs `ipmitool` on the provisioning host, not the target OS.
The controller therefore needs package-install privileges for the first run.

Copy `inventory/templates/hwmanage-bmc-secrets.yml` to
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

Paste [hwmanage-profile.json](../../../inventory/templates/hwmanage-profile.json)
into a NetBox config context and assign it to the intended device roles/tags.
It uses the existing Bifrost image URL/checksum, network defaults and root-disk
size hint. Its JSON is directly accepted by NetBox; no conversion is needed.

The `> 900` disk-size hint matches both 1 TB NVMe disks on SYS1412. To select
one specifically, set `properties.root_device.serial` in that device's local
config context to narrow the selection. A serial override is device-specific.

For direct Bifrost use, merge the same settings into its existing
`inventory/group_vars/baremetal` and apply node-specific overrides in the node
mapping. `inventory/templates/hwmanage-nodes.yml` shows the mapping format.
Keep installer DHCP/image-build/service configuration in Bifrost group vars;
it is separate from the node deployment profile.

## Individual node operations

NetBox is the default source except for `node list`, which defaults to Ironic.
Operations resolve the existing UUID rather than create a duplicate discovery.

```bash
hwmanage node show --limit SYS1412
hwmanage node enroll --limit SYS1412
hwmanage node sync --limit SYS1412
hwmanage node manage --limit SYS1412
hwmanage node inspect --limit SYS1412
hwmanage node clean --limit SYS1412
hwmanage node provide --limit SYS1412
hwmanage node deploy --limit SYS1412
```

`enroll` creates a missing registration without resetting an existing node's
state. `sync` updates approved fields without requesting a state transition.
`manage`, `inspect`, `provide`, `deploy` and `adopt` use native Ironic operations;
adoption is for an already installed system and is not a database-only import.

Manual cleaning defaults to partition/filesystem metadata removal. Supply native
clean steps as JSON, a JSON file or `-` for standard input:

```bash
hwmanage node clean --limit SYS1412 \
  --clean-steps '[{"interface":"deploy","step":"erase_devices_metadata"}]'
```

Individual actions support `--plan` to resolve/validate without applying the
operation. A plan can still read selected services or hardware identity.

## Provision an installed system

```bash
hwmanage provision -i netbox --limit SYS1412
hwmanage provision -i netbox --limit SYS1412 --tags manage_users
hwmanage provision -i netbox --limit SYS1412 --tags inventory
```

`provision` runs the repository's provisioning playbook. Role tags pass through
to Ansible; use the tags in [site.yml](site.yml.md). Inventory-only collection
requires its tools, including the BittWare SDK, to be installed already. Use full
provisioning before collecting a freshly deployed server.

Individual playbook commands accept `-e KEY=VALUE` and protected extra-variable
files. Target identity and scope cannot be overridden through extra variables:

```bash
hwmanage provision -i /provision/files.d/hosts.yml --limit SYS1412 \
  -e @/provision/files.d/overrides.yml
```

## Fixed runbooks

```bash
hwmanage run inspect-host -i ironic --limit <IRONIC_UUID>
hwmanage run provide-node -i netbox --limit SYS1412
hwmanage run full-provision -i netbox --limit SYS1412
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
hwmanage inventory export -i netbox --limit SYS1412 \
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

Run system checks on the provisioning host. Set `checks.boot_url` in `config.yml`
to a real served boot asset, such as `http://192.168.1.7:8080/ipa.kernel`:

```bash
hwmanage check systems
hwmanage check hosts -i netbox --limit SYS1412
hwmanage check hosts -i netbox --all
```

System checks read Ironic API/readiness, effective automatic-cleaning policy,
dnsmasq syntax, application-service status, NetBox access and the boot asset.
They report failures and do not repair services. Host checks use Ansible Linux
or Nexus management connectivity, rather than ICMP alone.

## Configure provisioning services

```bash
hwmanage config ironic --automated-clean false
hwmanage config dnsmasq add-host -i netbox --limit switch01
hwmanage config dnsmasq list-hosts
hwmanage config dnsmasq remove-host -i netbox --limit switch01
```

Explicit switch overrides use the boot-file path and boot-server address:

```bash
hwmanage config dnsmasq add-host -i netbox --limit switch01 \
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

## Controller configuration

The command and direct Ansible runs read `/provision/scripts/hwmanage/config.yml`.
Paths may be absolute or relative to that file. No shell exports are required.
The YAML sections select Ironic authentication/endpoint, platform file paths,
BMC/Vault credential paths, inventory source, Bifrost playbooks, new-device import
defaults, timeouts and service checks. `ironic.cloud` optionally selects an existing
OpenStack `clouds.yaml` entry; keep authentication secrets there.

```bash
hwmanage config show
hwmanage config validate
hwmanage --config /provision/files.d/site-controller.yml config show
hwmanage --config /provision/files.d/site-controller.yml inventory import --all --plan
```

`show` prints resolved settings without opening credential files. `validate`
checks schema and referenced paths, not service reachability or token validity.
Missing paths fail with their setting name. All keys are explicit; unknown keys
are rejected. Set `credentials.vault_password_file: null` only when no Vault
password file is needed. A `--config` file uses the full schema, not a partial overlay.

For direct Ansible, the same optional file is selected with an extra variable:

```bash
ansible-playbook -i localhost, playbooks/netbox/ironic_import.yml \
  -e hwmanage_all=true -e hwmanage_config_file=/provision/files.d/site-controller.yml
ansible-inventory -i inventory/dev_env/netbox-inv.yml --graph \
  -e hwmanage_config_file=/provision/files.d/site-controller.yml
```

The native NetBox inventory keeps a plain `api_endpoint` in
`inventory/dev_env/netbox-inv.yml`. Copy `netbox_url` from the platform endpoint
file there when it changes. This is the one deliberate duplicate connection
value; the wrapper reads the exported endpoint file. The inventory's token lookup
uses the credential-file path from central config.

`inventory.site_variables` selects the empty static inventory that loads adjacent
`group_vars`/`host_vars` alongside generated hosts. Roles, playbook selection and
provisioning settings stay in their existing files. Shared group vars and NetBox
playbook defaults reference central paths using the Ansible lookup bridge.
Normal explicit Ansible variable overrides still apply. Wrapper `--config` wins
over inherited connection environment settings; generated environment variables
are an internal interface to native tools and are restored after the command.

Lifecycle timeouts stop the workflow, not the underlying hardware operation.
Inspect state before repeating cleaning or deployment.

## NetBox connection files

Inside Bifrost, the platform export supplies two separate files:

```yaml
# /provision/files.d/platform-endpoints.yml
netbox_url: http://YOUR_NETBOX_HOST/mid-cbf-hw/netbox/
```

```yaml
# /provision/files.d/credentials/platform-secrets.yml
netbox_token: YOUR_NETBOX_API_TOKEN
```

Keep the secrets file protected with Ansible Vault. Select both file paths in the `platform` section of `config.yml`.
The URL is read from the endpoint file; it does not belong in the secrets file.

## Command output

Ansible output is shown as it runs. Import failures show their error or Python
traceback. Add `-v` to show other application output and Ansible detail; repeat
as `-vv` or `-vvv` for more Ansible detail:

```bash
hwmanage inventory import --all --plan -v
```

Application output and tracebacks may contain credentials or inventory data.
Keep terminal captures and the private diagnostic files local; redact before sharing.
Tasks elsewhere that explicitly protect secrets with `no_log` retain that setting.
