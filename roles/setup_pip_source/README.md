# setup_pip_source
Write a system-wide `pip.conf` pointing at the internal devpi caching proxy.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `pip_index_url` | _required_ | devpi `+simple` index URL |
| `pip_trusted_hosts` | `[]` | Hosts pip should not verify TLS for |
| `pip_ca_bundle` | `""` | Optional target PEM bundle; empty uses system trust |
| `pip_allow_insecure_http` | `false` | Explicit compatibility opt-in for an isolated HTTP index |
| `pip_config_file` | `/etc/pip.conf` | Target file |

Select `--tags setup_pip_source` in `playbooks/site.yml`.

Set these values in the inventory's distribution group vars:

```yaml
pip_index_url: "{{ platform_endpoints.pip_index_url }}"
pip_allow_insecure_http: true
pip_trusted_hosts: "{{ [pip_index_url | urlsplit('hostname')] }}"
pip_ca_bundle: ""
```

`platform_endpoints` is loaded from the generated controller-side
`platform-endpoints.yml` file by the inventory paths settings.

This permits HTTP only for the selected development cache. Restrict access to
the trusted LAN and keep credentials out of this system-wide configuration.
The platform cache mirrors public PyPI; its upstream HTTPS verification stays
enabled. Poetry project sources are configured separately.

HTTPS may be configured later: use an HTTPS URL, set
`pip_allow_insecure_http: false`, clear `pip_trusted_hosts` and trust the issuing
CA through system trust or `pip_ca_bundle`.
