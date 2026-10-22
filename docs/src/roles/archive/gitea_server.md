# midcbf.fhs.gitea_server

Gitea installed via Docker Compose, with optional pull-mirror creation
via the Gitea API.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `gitea_compose_dir` | `/etc/docker/compose/gitea` | Where compose project lives |
| `gitea_image` | `gitea/gitea:latest` | Container image |
| `gitea_http_port` | `3000` | HTTP port |
| `gitea_ssh_port` | `2222` | Container SSH port |
| `gitea_root_url` | `http://{{ gitea_domain }}:3000` | External URL |
| `gitea_admin_pat` | `""` | API token (required if mirrors set) |
| `gitea_mirrors` | `[]` | `[{upstream, name?}]` list |
| `gitea_mirrors_org` | `mirrors` | Org to put mirror repos in |
| `gitea_mirror_interval` | `1h` | Pull interval |

## Example

```yaml
gitea_admin_pat: "{{ vault_gitea_pat }}"
gitea_mirrors:
  - upstream: https://github.com/openstack/bifrost.git
  - upstream: https://gitlab.com/acme/physics-core.git
    name: physics-core
```

Tags: `gitea_server`, `install`, `config`.
