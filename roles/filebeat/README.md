# Filebeat

Run Elasticsearch index setup from the provisioning host using the same `.deb`
as the managed servers. Setup extracts the package temporarily; it does not
install Filebeat or start a service on the provisioning host.

## Configure

Set these in `inventory/dev_env/group_vars/device_roles_fpga-host-server/monitoring.yml`:

```yaml
filebeat_package_path: "{{ fhs_archives_dir }}/filebeat-9.5.5-amd64.deb"
filebeat_setup_credentials_file: "{{ platform_secrets_file }}"
filebeat_credentials_file: "{{ platform_secrets_file }}"
# Development LAN Elasticsearch service endpoint.
filebeat_elasticsearch_hosts: "{{ platform_endpoints.filebeat_elasticsearch_hosts }}"
```

Place the package under `/provision/files.d/external_archives/`. The Linux amd64
setup delegate defaults to `localhost` and needs `dpkg-deb` and access to
Elasticsearch. Development HTTP needs no internal CA installation. Credentials
travel unencrypted on the trusted LAN. HTTPS may be enabled later with CA trust.
Keep `filebeat_ssl_verification_mode: full`.

Use the generated `platform-secrets.yml` on the controller. Its setup credentials
are separate from the publishing identity within that one file:

```yaml
filebeat_elasticsearch_username: "filebeat_writer"
filebeat_elasticsearch_password: "<publishing-password>"
filebeat_setup_credentials:
  filebeat_elasticsearch_username: "elastic"
  filebeat_elasticsearch_password: "<setup-password>"
```

The [platform exporter](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/platform/charts/fhs-platform/README.md#export-ansible-settings)
writes these values from the installed platform. Encrypt the whole file and run
setup once:

```bash
ansible-vault encrypt /provision/files.d/credentials/platform-secrets.yml
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/filebeat_setup.yml --limit <HOST>
```

The exported setup identity is Elasticsearch's administrator. A separately
managed setup identity can instead use cluster `monitor`, `manage_ilm`,
`manage_index_templates` and index `manage` on `filebeat-*`, or a setup API key.
Only the publishing identity is rendered onto managed servers; the shared
secrets file and setup password remain on the controller.

Select one representative FPGA-role host to resolve its package/endpoint vars;
setup itself runs on the delegate and requires no SSH connection to that host.
Temporary package and credential files are removed after setup.

## Install collectors on managed servers

The publishing tasks read the top-level `filebeat_elasticsearch_username` and
`filebeat_elasticsearch_password` from the same encrypted platform secrets file.


Publishing credentials are written to root-only device
configuration; do not give devices the setup identity.

```bash
# Install the package, configure journald collection and start the device service.
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags filebeat
```

Device installation defaults to `filebeat_setup_enabled: false`: run the explicit
setup command first. Configuration and output connectivity are checked before
starting the service. The initial journal lookback is `filebeat_journald_since:
-1h`; an existing registry cursor takes precedence. Change these and other tuning
in group vars; generic defaults remain in [defaults/main.yml](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/roles/filebeat/defaults/main.yml).

For a future HTTPS endpoint, system CA trust is used by default. For explicit CA bundles,
`filebeat_setup_ssl_certificate_authorities` contains delegate paths and
`filebeat_ssl_certificate_authorities` contains device paths. Distribute public
certificates with [setup_platform_ca](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/roles/setup_platform_ca/README.md).

The optional Helm `logging.filebeatSetup.enabled` job also loads system-module
pipelines and the Kibana data view. Leave it disabled for Ansible index setup
alone; enable it deliberately when those additional assets are needed. Neither
setup path installs collectors. See [platform logging](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/platform/charts/fhs-platform/CONFIGURATION.md#logging).
