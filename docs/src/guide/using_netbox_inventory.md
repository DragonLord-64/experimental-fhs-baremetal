# Using NetBox For Ansible Inventory

NetBox owns device, interface, address and selected configuration facts. Protected controller files own authentication. The dynamic Ansible inventory and Bifrost export are separate consumers.

## 1. Configure Ansible inventory

Run these commands inside the provisioning container, from `/provision`.
Install the declared NetBox collections and Python requirements:

```bash
ansible-galaxy collection install -r playbooks/netbox/requirements.yml -p collections
python3 -m pip install -r playbooks/netbox/requirements.txt
```

Create a NetBox API token for the account used by Ansible. In
`inventory/dev_env/netbox-inv.yml`, set the endpoint and retain the device-role
filters/grouping already in that file:

```yaml
plugin: netbox.netbox.nb_inventory
api_endpoint: https://<NETBOX_HOST>/mid-cbf-hw/netbox/
validate_certs: true
interfaces: true
config_context: true
```

The inventory plugin reads its token from this same inventory file. Encrypt the
token interactively; this keeps it out of shell history:

```bash
ansible-vault encrypt_string --stdin-name value
```

Enter the token, then press Ctrl-D to finish input. Paste the resulting `value: !vault |` block
under `token` in `inventory/dev_env/netbox-inv.yml`, indented as follows:

```yaml
token:
  type: Bearer
  value: !vault |
    <encrypted output from encrypt_string>
```

Create the host `.vault_pass` file as described in the
[Bifrost quickstart](../bifrost-infra/QUICKSTART.md).
`bifrost-infra/docker-compose.yml` mounts this file at `/root/.vault_pass` and
configures Ansible to read it automatically:

```yaml
environment:
  - ANSIBLE_VAULT_PASSWORD_FILE=/root/.vault_pass
volumes:
  - ${VAULT_PASS_FILE:-../.vault_pass}:/root/.vault_pass:ro
```

The inventory plugin token is separate from the credentials file used by
import/export playbooks below.

If NetBox uses an internal CA, install its public certificate inside the
provisioning container before loading inventory:

```bash
sudo install -m 0644 /provision/files.d/certificates/platform-ca.crt \
  /usr/local/share/ca-certificates/platform-ca.crt
sudo update-ca-certificates
```

Alternatively set `ca_path: /provision/files.d/certificates/platform-ca.crt`
in `netbox-inv.yml`. Keep `validate_certs: true`.

### Read inventory and configure a server

1. Confirm the endpoint, device role groups and selected host scope.
2. Resolve the inventory privately. These commands contact NetBox but do not provision hosts:

   ```bash
   ansible-inventory -i inventory/dev_env/netbox-inv.yml --graph
   umask 077
   ansible-inventory -i inventory/dev_env/netbox-inv.yml --list --output <PRIVATE_OUTPUT_PATH>
   ```

3. Inspect host/group membership privately, then select an exact role and host:

   ```bash
   ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/provision.yml --limit <HOST> --tags manage_users
   ```

Inventory output can contain secrets. Keep it outside Git and build artifacts. Config context does not override every Ansible variable source; confirm resolved precedence. The inventory does not create `fhs_nodes` automatically.

Discovery imports native rack positions, interfaces and network/power cables;
Inventory assets retain physical identity and module metadata. Optional server
`rack_unit` and independent `power_ports` mappings are documented in the
[importer schema](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/playbooks/netbox/README.md#optional-server-placement-and-power).
Use the unified importer's compare/apply workflow before polling the updated
inventory. Neither Topology Views filters nor an Inventory API prerequisite
failure establish a physical connection.


## 2. Configure import/export credentials

Import/export playbooks read a separate YAML file. Create it on the provisioning
host's resource mount (inside the container it is `/provision/files.d`):

```bash
install -d -m 0700 /provision/files.d/credentials
umask 077
vi /provision/files.d/credentials/mid-cbf-hw-netbox.yml
```

Use these exact variable names in that file:

```yaml
netbox_url: https://<NETBOX_HOST>/mid-cbf-hw/netbox/
netbox_token: "<NetBox API token>"
netbox_validate_certs: true
```

Encrypt the file after saving it:

```bash
ansible-vault encrypt /provision/files.d/credentials/mid-cbf-hw-netbox.yml
```

`playbooks/netbox/defaults.yml` assigns the credentials file for import and
export plays:

```yaml
netbox_credentials_file: /provision/files.d/credentials/mid-cbf-hw-netbox.yml
```

To select another file for one run, add
`-e netbox_credentials_file=/provision/files.d/credentials/<name>.yml`.
The inventory plugin does not load this file.

## 3. Export servers for Bifrost

Create `/provision/files.d/credentials/redfish.yml` for BMC authentication:

```yaml
redfish_credentials:
  defaults:
    redfish_username: "<BMC username>"
    redfish_password: "<BMC password>"
  devices:
    <NetBox-device-name>:
      redfish_username: "<override username>"
      redfish_password: "<override password>"
```

Omit `devices` when all selected servers use the defaults. Encrypt this file:

```bash
ansible-vault encrypt /provision/files.d/credentials/redfish.yml
# Write a private YAML inventory for Bifrost; no enrollment or imaging occurs.
ansible-playbook -i localhost, playbooks/netbox/bifrost_export.yml \
  -e netbox_credentials_file=/provision/files.d/credentials/mid-cbf-hw-netbox.yml \
  -e redfish_credentials_file=/provision/files.d/credentials/redfish.yml \
  -e bifrost_output=/provision/files.d/bifrost/baremetal.yml
```

The export selects NetBox device type `TeraBox1501b` and interfaces tagged
`provisioning-interface`. Set `bifrost_device_type` in `playbooks/netbox/defaults.yml`
or pass `-e bifrost_device_type=<device-type>` to select another type. Devices
need native out-of-band/primary addresses and valid unique provisioning MACs.
The output contains BMC credentials: its mode is `0600`, and a newly created
output directory is `0700`. Keep it outside Git. Enrollment and imaging are
separate Bifrost commands.

See [development playbooks](../playbooks/development.md) for discovery/import and switch POAP, and [provisioning design](../design/provisioning-interface.md) for the intended physical sequence.

Source files: `inventory/dev_env/netbox-inv.yml` and `playbooks/netbox/bifrost_export.yml`.
