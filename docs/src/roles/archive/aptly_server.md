# midcbf.fhs.aptly_server

Install + configure an aptly repository server. Generates a signing key
on first run, optionally serves the REST API over HTTP via systemd.

Mirror/snapshot/publish operations are driven by `aptly_mirrors`,
`aptly_snapshots`, `aptly_publishes` lists — see defaults for shape.

## Variables (key ones)

| Var | Default | Purpose |
|---|---|---|
| `aptly_user` / `aptly_group` | `aptly` | Service account |
| `aptly_home` | `/var/aptly` | Data dir + GPG home |
| `aptly_gpg_email` | `fhs-aptly@local.invalid` | Signing key identity |
| `aptly_mirrors` | `[]` | Mirrors to create |
| `aptly_serve_http` | `false` | Enable `aptly api serve` via systemd |
| `aptly_serve_listen` | `:8082` | HTTP listen spec |

Tags: `aptly_server`, `install`, `config`.
