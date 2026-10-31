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
Keep switches out of Linux policy groups.

## Trust NetBox before loading inventory

Install the public issuing CA inside the provisioning container first. Inventory
loads before any target role can run, so the target CA role cannot bootstrap
this connection.

```bash
sudo install -m 0644 /provision/files.d/certificates/platform-ca.crt \
  /usr/local/share/ca-certificates/platform-ca.crt
sudo update-ca-certificates
ansible-inventory -i inventory/dev_env/netbox-inv.yml --graph
```

Keep `validate_certs: true` in `netbox-inv.yml`. Alternatively set its `ca_path`
to the controller's PEM CA bundle. Set `api_endpoint: https://<NETBOX_HOST>/mid-cbf-hw/netbox/` and a Vault-encrypted
`token` in that inventory file. The [NetBox guide](../docs/src/guide/using_netbox_inventory.md)
shows the token format and separate import/export credentials.

## Configure clients

Edit `inventory/dev_env/group_vars/device_roles_fpga-host-server/distribution.yml`
for APT/pip/Git settings and `monitoring.yml` in the same directory for package
paths and Elasticsearch. Dedicated HTTPS ingress hostnames in the
example require matching DNS records and certificates.
The site's LoadBalancer DNS integration supplies external service addresses;
verify the configured release/namespace names from the provisioning host and targets.

To install the public CA on managed servers, set this in `all/paths.yml`:

```yaml
platform_ca_certificates:
  - src: "{{ fhs_resources_dir }}/certificates/platform-ca.crt"
    name: platform-ca
```

```bash
# Inspect scope, then configure CA trust and package/Git access.
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --list-hosts --tags distribution
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags distribution
```

See [platform installation](../platform/charts/fhs-platform/README.md),
[Filebeat setup](../roles/filebeat/README.md) and
[site tags](../docs/src/playbooks/site.yml.md).
