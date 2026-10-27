# manage_users

Creates FHS accounts from controller-local public key files, configures sudo and adds the Ansible user to the shared BittWare group. Other memberships are preserved.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `fhs_keys_dir` | Empty (required) | Controller directory containing `username.pub` files; at least one is required |
| `fhs_user_groups` | `[sudo, bittware]` | Groups assigned to managed users |
| `fhs_sudoers_file` | `/etc/sudoers.d/99-fhs-passwordless` | Sudoers drop-in, checked with visudo |
| `fhs_development_passwordless_sudo` | `false` | Opt in only approved key-file accounts to passwordless development sudo |
| `fhs_sudoers_content` | Generated named-user policy | Optional explicit sudo policy override |
| `fhs_bittware_group` / `fhs_bittware_group_gid` | `bittware` / `666` | Shared SDK/runner identity |
| `vault_user_password_<username>` | `!` | Optional protected password hash for each discovered user |

`fhs_users: []` remains in defaults but is not consumed by `tasks/main.yml`. Accounts and SSH keys are derived from `*.pub` filenames and contents, not that list.

## Workflow

1. Set `fhs_keys_dir` explicitly and place one `username.pub` per approved account there. The development inventory selects `/provision/files.d/dev-ssh-keys.d`; production has no default development key directory.
2. Supply any password hashes through protected variables.
3. From `/provision`, select the host and role:

   ```bash
   ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags manage_users
   ```

The wrapper tag selects the whole role. Account creation defaults to a locked password. `inventory/dev_env/group_vars/all.yml` explicitly enables passwordless sudo for the accounts discovered in the approved development key directory; production must leave that option false. A custom `fhs_sudoers_content` overrides the generated policy. SSH connections reset after membership changes. The role does not remove accounts absent from the key directory.
