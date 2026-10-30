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

Use `https://<devpi-host>/root/pypi/+simple/` through the platform ingress.
Install the issuing CA first with `--tags setup_platform_ca`. Leave `pip_trusted_hosts` empty with
trusted TLS; setting it bypasses certificate checks. The platform cache serves
public PyPI only. Poetry project sources are configured separately. Keep
credentials out of this world-readable system configuration.
