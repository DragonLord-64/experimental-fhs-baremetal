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

The `filebeat` tag is supplied by the site wrapper; the role has no internal phase tags. Installation validates configuration and, by default, the output connection before starting the service. This role was not exercised by the synthetic monitoring validation.
