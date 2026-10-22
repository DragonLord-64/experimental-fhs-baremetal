# Setup Pip Source

Write a system-wide `pip.conf` pointing at the internal devpi caching proxy.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `pip_index_url` | _required_ | devpi `+simple` index URL |
| `pip_trusted_hosts` | `[]` | Hosts pip should not verify TLS for |
| `pip_config_file` | `/etc/pip.conf` | Target file |

Tags: `pip_index`, `config`.
