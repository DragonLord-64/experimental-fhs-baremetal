# setup_git_proxy

Configure Git system-wide to send HTTP and HTTPS repository traffic through
the internal Squid forward proxy.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `git_proxy_url` | _required_ | Squid proxy URL, including its port |
| `git_url_rewrites` | `[]` | System-wide URL rewrite entries (`target` and `instead_of`) |

Tags: `git_proxy`, `config`.
