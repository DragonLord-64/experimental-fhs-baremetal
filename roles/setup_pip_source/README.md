# setup_pip_source
Write a system-wide `pip.conf` pointing at the internal devpi caching proxy.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `pip_index_url` | _required_ | devpi `+simple` index URL |
| `pip_trusted_hosts` | `[]` | Hosts pip should not verify TLS for |
| `pip_config_file` | `/etc/pip.conf` | Target file |

Select `--tags setup_pip_source` in `playbooks/site.yml`.

Use `http://<devpi-host>:3141/root/pypi/+simple/` on an isolated provisioning
network, or an approved HTTPS endpoint. Leave `pip_trusted_hosts` empty with
trusted TLS; setting it bypasses certificate checks. The platform cache serves
public PyPI only. Poetry project sources are configured separately. Keep
credentials out of this world-readable system configuration.
