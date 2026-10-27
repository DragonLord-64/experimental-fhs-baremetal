# filebeat

Installs a controller-local Filebeat Debian package, collects the systemd journal and publishes logs to Elasticsearch. See `tasks/main.yml` and `templates/filebeat.yml.j2`.

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `filebeat_package_path` | `/provision/files.d/external_archives/filebeat-9.5.5-amd64.deb` | Controller package |
| `filebeat_expected_major_version` | `9` | Required installed major version |
| `filebeat_config_path` | `/etc/filebeat/filebeat.yml` | Configuration path |
| `filebeat_validate_output` | `true` | Test configured Elasticsearch connectivity |
| `filebeat_journald_seek` | `since` | Initial journal position |
| `filebeat_journald_since` | `-1h` | Initial lookback; existing registry cursor wins |
| `filebeat_ssl_verification_mode` | `full` | TLS certificate verification |

Set `filebeat_elasticsearch_hosts` for the target environment and supply `filebeat_credentials_file` privately; see `defaults/main.yml`. The original endpoint is not a VM override. Credentials are read on the controller and are not part of examples.

## Command and tags

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags filebeat
```

The `filebeat` tag is supplied by the site wrapper; the role has no internal phase tags. Installation validates configuration and, by default, the output connection before starting the service. Stage-5 checks use the real pinned Debian package and validate installation,
configuration and a process start without a live Elasticsearch endpoint. Live
index-management compatibility, publishing and journal ingestion remain unvalidated;
the disposable container service fixture is not systemd.

## Elasticsearch setup

Before starting device services, the role runs `filebeat setup --index-management`
once per play batch on `filebeat_setup_delegate` (default `localhost`), without
become. Use the normal linear strategy and one shared endpoint/package per play.
The delegate needs Linux amd64, `dpkg-deb`, and access to Elasticsearch. It extracts
the exact `filebeat_package_path` installed on devices into a private temporary
directory; no control-host Filebeat service is installed. Temporary files are
removed even when setup fails. Setup runs on each invocation, preserves existing
templates and ILM policies, and reports changed; check mode skips it.

Supply a separate Vault-capable `filebeat_setup_credentials_file` on the controller
(default `/provision/files.d/credentials/filebeat-setup.yml`) containing either:

```yaml
filebeat_elasticsearch_api_key: "<id>:<api_key>"
```

or `filebeat_elasticsearch_username` and `filebeat_elasticsearch_password`.
These are setup credentials only; devices continue using the publishing credentials
in `filebeat_credentials_file`. The role consumes existing credentials; it does
not create users or API keys. Secret tasks suppress output and diffs.

The setup identity needs cluster `monitor`, `manage_ilm`, `manage_index_templates`
and index `manage` on `filebeat-*`. See Elastic's
[setup privileges](https://www.elastic.co/docs/reference/beats/filebeat/privileges-to-setup-beats).
Publishers need cluster `monitor` and index `create_doc`, `auto_configure` on
`filebeat-*`; the device configuration skips ILM existence checks. See
[publishing privileges](https://www.elastic.co/docs/reference/beats/filebeat/privileges-to-publish-events).
Keep setup privileges off device accounts. Use HTTPS for authenticated endpoints.
Set `filebeat_setup_ssl_certificate_authorities` to CA paths on the delegate;
`filebeat_ssl_certificate_authorities` contains paths on devices.

This loads the package's default versioned template, data stream and ILM policy.
The journald input uses no module ingest pipelines or Kibana dashboards. Set
`filebeat_setup_enabled: false` only when index management is already provisioned.

Offline delegated setup fixture (requires Ansible, Python PyYAML and `dpkg-deb`):

```bash
python3 -m unittest discover -s ops/platform/logging -p test_role_setup.py -v
```

The fixture checks API-key/password setup, delegation to localhost, private config,
failure cleanup and check-mode skipping. It does not establish live Elasticsearch
compatibility or device journal ingestion.
