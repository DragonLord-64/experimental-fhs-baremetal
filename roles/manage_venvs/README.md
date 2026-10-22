# manage_venvs

Create shared Python virtual environments. Use versioned package specs
(`name==1.2.3`) for full idempotency.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `venvs` | `[]` | List of venv specs (see below) |
| `venv_apt_packages` | `[python3-venv, python3-pip]` | Host prerequisites |

Per-entry keys: `path` (required), `python` (required interpreter path),
`owner`, `group`, `mode`, `packages`.

## Example

```yaml
venvs:
  - path: /opt/venvs/fhs
    python: /usr/bin/python3.10
    owner: root
    group: bittware
    mode: "0775"
    packages:
      - pip==24.2
      - setuptools==75.1.0
      - wheel==0.44.0
```

Tags: `venvs`, `install`, `config`.
