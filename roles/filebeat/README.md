# Filebeat

Run Elasticsearch index setup from the provisioning host using the same `.deb`
as the managed servers. Setup extracts the package temporarily; it does not
install Filebeat or start a service on the provisioning host.

## Configure

Set these in `inventory/dev_env/group_vars/device_roles_fpga-host-server/monitoring.yml`:

```yaml
filebeat_package_path: "{{ fhs_archives_dir }}/filebeat-9.5.5-amd64.deb"
filebeat_setup_credentials_file: "{{ fhs_credentials_dir }}/filebeat-setup.yml"
filebeat_credentials_file: "{{ fhs_credentials_dir }}/filebeat.yml"
# Filebeat defaults to port 9200; specify :443 for the HTTPS ingress.
filebeat_elasticsearch_hosts: ["https://<elasticsearch-hostname>:443"]
```

Place the package under `/provision/files.d/external_archives/`. The Linux amd64
setup delegate defaults to `localhost` and needs `dpkg-deb`, CA trust and access
to Elasticsearch. [Install controller trust first](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/inventory/README.md).
Keep `filebeat_ssl_verification_mode: full`.

Create `/provision/files.d/credentials/filebeat-setup.yml` with an existing setup
identity:

```yaml
filebeat_elasticsearch_username: "<setup-user>"
filebeat_elasticsearch_password: "<setup-password>"
```

Alternatively supply only `filebeat_elasticsearch_api_key: "<id>:<api_key>"`.
The setup identity needs cluster `monitor`, `manage_ilm`, `manage_index_templates`
and index `manage` on `filebeat-*`. These credentials remain on the controller.

```bash
# Encrypt the credentials, then load the template and lifecycle policy once.
ansible-vault encrypt /provision/files.d/credentials/filebeat-setup.yml
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/filebeat_setup.yml --limit <HOST> --ask-vault-pass
```

Select one representative FPGA-role host to resolve its package/endpoint vars;
setup itself runs on the delegate and requires no SSH connection to that host.
Temporary package and credential files are removed after setup.

## Install collectors on managed servers

Create a separate `/provision/files.d/credentials/filebeat.yml`:

```yaml
filebeat_elasticsearch_username: filebeat_writer
filebeat_elasticsearch_password: "<platform-filebeat-password>"
```

Match the platform credential's `filebeat-password` value. Encrypt this file with
Ansible Vault too. Publishing credentials are written to root-only device
configuration; do not give devices the setup identity.

```bash
# Install the package, configure journald collection and start the device service.
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags setup_platform_ca,filebeat --ask-vault-pass
```

Device installation defaults to `filebeat_setup_enabled: false`: run the explicit
setup command first. Configuration and output connectivity are checked before
starting the service. The initial journal lookback is `filebeat_journald_since:
-1h`; an existing registry cursor takes precedence. Change these and other tuning
in group vars; generic defaults remain in [defaults/main.yml](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/roles/filebeat/defaults/main.yml).

System CA trust is used by default. For explicit CA bundles,
`filebeat_setup_ssl_certificate_authorities` contains delegate paths and
`filebeat_ssl_certificate_authorities` contains device paths. Distribute public
certificates with [setup_platform_ca](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/roles/setup_platform_ca/README.md).

The optional Helm `logging.filebeatSetup.enabled` job also loads system-module
pipelines and the Kibana data view. Leave it disabled for Ansible index setup
alone; enable it deliberately when those additional assets are needed. Neither
setup path installs collectors. See [platform logging](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/platform/charts/fhs-platform/CONFIGURATION.md#logging).
