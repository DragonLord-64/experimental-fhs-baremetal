# manage_users

Creates FHS accounts from controller-local public key files, configures sudo and adds the Ansible user to `bittware`.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `fhs_keys_dir` | `/provision/files.d/dev-ssh-keys.d` | Controller directory containing `username.pub` files; at least one is required |
| `fhs_user_groups` | `[sudo, bittware]` | Groups assigned to managed users |
| `fhs_sudoers_file` | `/etc/sudoers.d/99-fhs-passwordless` | Sudoers drop-in, checked with visudo |
| `fhs_sudoers_content` | `"%sudo ALL=(ALL) NOPASSWD:ALL\n"` | Passwordless sudo policy |
| `vault_user_password_<username>` | `!` | Optional protected password hash for each discovered user |

`fhs_users: []` remains in defaults but is not consumed by `tasks/main.yml`. Accounts and SSH keys are derived from `*.pub` filenames and contents, not that list.

## Workflow

1. Place the public keys in `fhs_keys_dir`, one `username.pub` per account.
2. Supply any password hashes through protected variables.
3. From `/provision`, select the host and role:

   ```bash
   ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags manage_users
   ```

The wrapper tag selects the whole role. Internal tags: `users`, `install`, `config`. Account creation defaults to a locked password; the default sudo policy is passwordless. The role does not remove accounts absent from the key directory.
