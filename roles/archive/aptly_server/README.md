# OBSOLETE: aptly_server

**This role is obsolete.** It is maintained for historical purposes only. Do not use this role for new deployments.

Historically, this role was used to install and configure an aptly repository server, including the generation of signing keys and the optional setup of the REST API over HTTP via systemd.

For detailed configuration parameters, see the [role documentation](/docs/src/roles/archive/aptly_server.md).

Tags: `aptly_server`, `install`, `config`.


# aptly_server (OBSOLETE)

Historically used to install and configure an aptly repository server. It handled the generation of a signing key on first run and optionally provided a service to serve the REST API over HTTP via systemd.

Mirror, snapshot, and publish operations are driven by lists defined in the defaults.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `aptly_user` / `aptly_group` | `aptly` | Service account for running the process |
| `aptly_home` | `/var/aptly` | Data directory and GPG home |
| `aptly_gpg_email` | `fhs-aptly@local.invalid` | Identity for the auto-generated signing key |
| `aptly_mirrors` | `[]` | List of mirror configurations to create |
| `aptly_snapshots` | `[]` | List of snapshots to create from mirrors |
| `aptly_publishes` | `[]` | List of publish endpoints (snapshots/mirrors) |
| `aptly_serve_http` | `false` | Whether to enable `aptly api serve` via systemd |
| `aptly_serve_listen` | `:8082` | The address/port the HTTP API listens on |

Tags: `aptly_server`, `install`, `config`.