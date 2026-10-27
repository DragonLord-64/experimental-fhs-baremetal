# setup_git_proxy

Configure Git system-wide to send HTTP and HTTPS repository traffic through
the internal Squid forward proxy.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `git_proxy_url` | _required_ | Squid proxy URL, including its port |
| `git_url_rewrites` | `[]` | System-wide URL rewrite entries (`target` and `instead_of`) |

Select `--tags setup_git_proxy` in `playbooks/site.yml`.

Use `http://<proxy-host>:3128`. The platform allows HTTPS CONNECT only to
configured Git domains on 443; Git still verifies the origin TLS certificate.
No TLS interception or proxy authentication is configured. Restrict access to
provisioning clients and keep credentials out of the system proxy URL.
