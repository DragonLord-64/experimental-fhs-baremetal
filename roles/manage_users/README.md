# Users and BittWare environments

Create managed accounts, install the system SDK and prepare BittWare tools with
one role. Each public-key account, explicit account and the Ansible account gets
`~/.bw_venv`; the shared environment is `/opt/venvs/fhs`.

## Configure

Put `username.pub` files under `fhs_keys_dir`. In the device-role
`environment.yml`, select the SDK and additional accounts:

```yaml
fpga_bittware_sdk_deb: "{{ fhs_archives_dir }}/bittware-sdk-ubuntu24.04-2026.1.0.deb"
fpga_update_bittware_sdk: true
fhs_user_venv_name: .bw_venv
fhs_shared_venv_path: /opt/venvs/fhs
fhs_shared_venv_owner: ubuntu
fhs_users:
  - name: gitlab-runner
    system: true
    groups: [bittware]
```

Additional accounts accept `group`, `groups`, `home`, `shell`, protected
`password` and `ssh_keys`. Keep the existing local account/password entry if
required. Public-key accounts use `vault_user_password_<username>` or a locked
password. Existing supplementary groups and SSH keys are preserved.

## Run

```bash
# Configure package access first, then accounts and all SDK environments.
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags distribution,manage_users --ask-vault-pass
# Subsequent account or SDK updates, with package access already configured.
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags manage_users --ask-vault-pass
```

Set `fpga_update_bittware_sdk: false` to use an already installed SDK. The role
activates each environment and runs `bw_pip install` as its owner with
`BWSDK_ROOT` set. SDK version changes, missing tooling or broken dependencies
trigger installation again. Successful environments are checked on every run.
The shared environment is readable/executable by the BittWare group; personal
ones belong to their users. No GitLab registration or runner service is installed.

```bash
# Activate your tools when needed; login shell startup is unchanged.
source ~/.bw_venv/bin/activate
```

`fhs_setup_user_environments: false` selects account/access setup only.
Development passwordless sudo remains an explicit opt-in through
`fhs_development_passwordless_sudo`; service accounts are excluded from its
public-key policy. `fhs_sudoers_content` can override the policy. Task files split
accounts, SDK packages, shared/personal environments and installation checks.
