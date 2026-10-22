# Setup Git Proxy

Configure Git system-wide to send HTTP and HTTPS repository traffic through
the internal Squid forward proxy.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `git_proxy_url` | _required_ | Squid proxy URL, including its port |

Tags: `git_proxy`, `config`.
