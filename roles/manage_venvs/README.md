# manage_venvs

The site provisioning workflow now uses `manage_users`
for accounts, system SDK and all BittWare environments. This standalone role
remains for existing direct callers; use `--tags manage_users` with `site.yml`.

Create shared Python virtual environments. Use versioned package specs
(`name==1.2.3`) for full idempotency.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `venvs` | `[]` | List of venv specs (see below) |
| `venv_apt_packages` | `[python3-venv, python3-pip]` | Host prerequisites |

Per-entry keys: `path` (required), `python` (required interpreter path),
`owner`, `group`, `mode`, `packages`. Defaults: owner `root`, group `bittware`,
mode `0750`. The owner installs packages. Ownership and permissions are repaired
throughout the venv without following interpreter symlinks. Directory group/other
access controls the tree; `X` keeps data files non-executable. Optional `tree_mode`
overrides those tree permissions. Parent directories must permit owner traversal.

## Example

```yaml
venvs:
  - path: /opt/venvs/fhs
    python: /usr/bin/python3
    owner: root
    group: bittware
    mode: "0750"
    packages:
      - pip==24.2
      - setuptools==75.1.0
      - wheel==0.44.0
```

Tags: `venvs`, `install`, `config`.

A group-writable venv contains writable executable code. Do not execute it as
root or from a privileged service; use a dedicated unprivileged owner. Existing
users/groups must be created first. The permission fixture uses a local package
and SDK stand-in; it does not validate proprietary software or FPGA hardware.
