# Inventory

Run commands from the repository root inside the provisioning environment.
`RESOURCES_DIR` on the provisioning host is mounted at `/provision/files.d` in
the container. Keep packages, public CA certificates and private credential files
there; keep site settings in group vars.

## Configure the environment

```text
inventory/dev_env/
  netbox-inv.yml                 # current NetBox API and vaulted token
  hosts.yml                      # reference snapshot; runtime hosts come from NetBox
  group_vars/
    all/
      connections.yml
      paths.yml                  # /provision/files.d and shared directories
    device_roles_fpga-host-server/
      artifacts.yml
      distribution.yml           # APT, pip and Git endpoints
      environment.yml
      hardware.yml
      identity.yml
      monitoring.yml             # packages, Elasticsearch and credential paths
      network.yml
      runtime.yml
  host_vars/                     # deliberate per-server overrides
```

Ansible loads every YAML file in a group's directory. Put a variable in one
file; use host vars only when a server needs a different value. Review the
existing connection and identity settings before copying them to another site.

`hosts.yml` contains reference snapshots. Use NetBox for runtime hosts and role
membership.

`hosts.yml` defines `ubuntu24_cis_production → linux_servers →
device_roles_fpga-host-server`, with additional explicit Linux server groups.
The standard commands below load only the NetBox plugin. If you need
additional static inheritance, use an explicitly reviewed groups-only file and pass that file as a second `-i` argument. Site plays
target `device_roles_fpga-host-server`; CIS targets `ubuntu24_cis_production`.
For NetBox inventory, assign the tag with slug `ubuntu24-hardening` to each
Ubuntu 24.04 server intended for CIS hardening. This creates membership in
`ubuntu24_cis_production` independently of device role. Devices must be active
and have a primary IP address. Review the selected hosts before applying:

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --list-hosts --tags ubuntu24_cis
```

Keep switches out of Linux policy groups.

## Configure NetBox inventory

Use the [platform exporter](../platform/charts/fhs-platform/README.md#export-ansible-settings)
and copy its two files to the controller. Encrypt `credentials/platform-secrets.yml`.
Copy `netbox_url` from `platform-endpoints.yml` into `api_endpoint` in
`netbox-inv.yml`; its token lookup reads the shared secrets file. The development platform uses HTTP; no internal CA
installation is required. Keep `validate_certs: true` for a future HTTPS endpoint.
The [NetBox guide](../docs/src/guide/using_netbox_inventory.md) shows the shared-file
format and import/export settings.

```bash
ansible-inventory -i inventory/dev_env/netbox-inv.yml --graph
```

## Configure clients

Edit `inventory/dev_env/group_vars/device_roles_fpga-host-server/distribution.yml`
for APT/pip/Git settings and `monitoring.yml` in the same directory for package
paths and Elasticsearch. Internal endpoints use HTTP on the trusted development LAN.
The site's LoadBalancer DNS integration supplies external service addresses;
verify the configured release/namespace names from the provisioning host and targets.

For a future HTTPS deployment only, public CA distribution can be configured in `all/paths.yml`:

```yaml
platform_ca_certificates:
  - src: "{{ fhs_resources_dir }}/certificates/platform-ca.crt"
    name: platform-ca
```

```bash
# Inspect scope, then configure package/Git access.
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --list-hosts --tags distribution
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags distribution
```

See [platform installation](../platform/charts/fhs-platform/README.md),
[Filebeat setup](../roles/filebeat/README.md) and
[site tags](../docs/src/playbooks/site.yml.md).

## Hardware management templates

- [NetBox deployment profile (JSON)](templates/hwmanage-profile.json): paste into
  an active NetBox Config Context. Uses the existing Bifrost image URL/checksum,
  subnet/DNS and root-disk size hint. Assign it to the intended device role/tag.
- [Native node inventory (YAML)](templates/hwmanage-nodes.yml): per-node identity
  and address example using the same deployment defaults.
- [BMC credential format](templates/hwmanage-bmc-secrets.yml): copy outside Git,
  fill in the login and protect it with Vault. Select its path in hwmanage config.

The shared disk hint is `> 900` GB. For hosts with multiple matching disks,
select the intended OS disk with a device-specific `properties.root_device.serial`.
