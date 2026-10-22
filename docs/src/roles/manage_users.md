# Manage Users

Creates FHS user accounts with sudo + SSH keys.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `fhs_users` | `[]` | List of `{name, password, ssh_keys}` dicts |
| `fhs_user_groups` | `[sudo, bittware]` | Groups every user is added to |
| `fhs_sudoers_file` | `/etc/sudoers.d/10-sudo-group` | Sudoers drop-in path |
| `fhs_sudoers_content` | `"%sudo ALL=(ALL) ALL\n"` | Sudoers drop-in body |

## Example

```yaml
fhs_users:
  - name: alice
    password: "$6$..."
    ssh_keys:
      - "ssh-ed25519 AAAA... alice@laptop"
```

Tags: `users`, `install`, `config`.
