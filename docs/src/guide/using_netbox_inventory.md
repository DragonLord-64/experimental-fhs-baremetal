# Using NetBox For Ansible Inventory

NetBox owns device, interface, address and selected configuration facts. Protected controller files own authentication. The dynamic Ansible inventory and Bifrost export are separate consumers.

## Polling NetBox for Inventory

`inventory/dev_env/netbox-inv.yml` uses `netbox.netbox.nb_inventory`. It enables interfaces, IP addresses, config context, flattened custom fields and extra variables. It selects active devices with primary IPs, groups by device role and adds `teraboxes` / `nexus` from the `fpga-host-server` / `nexus-switch` category tags (legacy role grouping remains supported).

A minimal private configuration is:

```yaml
plugin: netbox.netbox.nb_inventory
api_endpoint: https://<NETBOX_HOST>/netbox/
token: <TOKEN_FROM_PROTECTED_CONFIGURATION>
validate_certs: true
interfaces: true
config_context: true
```

The tracked development configuration uses a Vault-encrypted bearer token and enables certificate validation. Install the public issuing CA in the provisioning host/container before loading inventory, or set `ca_path` to its PEM bundle. See [controller trust](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/inventory/README.md#trust-netbox-before-loading-inventory). Replace the old preserved Vault token with one issued by the new NetBox deployment. Supply its Vault password privately; do not copy tokens into commands or published inventory output. Install the collection from `requirements.yml` and its Python dependencies before polling.

## Workflow

1. Confirm the endpoint, device role groups and selected host scope.
2. Resolve the inventory privately. These commands contact NetBox but do not provision hosts:

   ```bash
   ansible-inventory -i inventory/dev_env/netbox-inv.yml --ask-vault-pass --graph
   umask 077
   ansible-inventory -i inventory/dev_env/netbox-inv.yml --ask-vault-pass --list --output <PRIVATE_OUTPUT_PATH>
   ```

3. Inspect host/group membership privately, then select an exact role and host:

   ```bash
   ansible-playbook -i inventory/dev_env/netbox-inv.yml --ask-vault-pass playbooks/provision.yml --limit <HOST> --tags manage_users
   ```

Inventory output can contain secrets. Keep it outside Git and build artifacts. Config context does not override every Ansible variable source; confirm resolved precedence. The inventory does not create `fhs_nodes` automatically.

Discovery imports native rack positions, interfaces and network/power cables;
Inventory assets retain physical identity and module metadata. Optional server
`rack_unit` and independent `power_ports` mappings are documented in the
[importer schema](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/playbooks/netbox/README.md#optional-server-placement-and-power).
Use the unified importer's compare/apply workflow before polling the updated
inventory. Neither Topology Views filters nor an Inventory API prerequisite
failure establish a physical connection.


## Inventory consumers

```{mermaid}
flowchart TD
    N[NetBox records] -->|inventory plugin| A[Ansible inventory]
    A -->|selected hosts and roles| C[Installed OS configuration]
    N -->|device and interface facts| X[Bifrost export playbook]
    R[Protected Redfish credentials] -->|authentication| X
    X -->|mode 0600| Y[Private Bifrost YAML]
```

The two outputs have different consumers. Writing YAML does not enroll or image a server.

## Provisioning export ownership

`playbooks/netbox/bifrost_export.yml` reads NetBox and writes Bifrost-compatible YAML. It selects a device type (default `TeraBox1501b`) and interfaces tagged `provisioning-interface`, reads native out-of-band and primary IPv4 addresses, and combines approved custom fields with protected Redfish credentials. Simulated devices are rejected. It validates MAC uniqueness and required fields before writing mode `0600` output; a newly created output directory is mode `0700`.

```bash
ansible-playbook playbooks/netbox/bifrost_export.yml --ask-vault-pass \
  -e netbox_credentials_file=<PRIVATE_NETBOX_VARS> \
  -e redfish_credentials_file=<PRIVATE_REDFISH_VARS> \
  -e bifrost_output=<PRIVATE_OUTPUT_PATH>
```

The existing private file `/provision/files.d/credentials/mid-cbf-hw-netbox.yml`
must use the new deployment URL (`https://<NETBOX_HOST>/mid-cbf-hw/netbox/`) and
a token issued there. The protected files supply `netbox_url`, `netbox_token` and `redfish_credentials` (`defaults` and optional per-device entries). The default output is `playbooks/netbox/output/baremetal.yml`; always choose a protected destination. Export does not enroll, deploy or modify NetBox. Enrollment and imaging remain separate Bifrost operations. No implemented post-provisioning role-to-IP deployment export is established by this playbook.

See [development playbooks](../playbooks/development.md) for discovery/import and switch POAP, and [provisioning design](../design/provisioning-interface.md) for the intended physical sequence.

Source files: `inventory/dev_env/netbox-inv.yml` and `playbooks/netbox/bifrost_export.yml`.
