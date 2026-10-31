# manage_venvs (retired)

Use `manage_users` for accounts, the system SDK and BittWare environments:

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags manage_users
```

Configure `fhs_users` and SDK/environment settings in environment group vars.
The old role entry point fails with a migration message instead of running a
second implementation. No active site play calls this role.
