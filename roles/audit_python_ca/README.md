# audit_python_ca

Read-only check for the October 2026 eMudhra/emSign certificate incident on Ubuntu
24.04. `site.yml` runs it after provisioning. It reports findings before failing;
it never updates certificates, removes venvs or installs packages.

```sh
ansible-playbook -i inventory/dev_env/hosts.yml playbooks/audit_python_ca.yml
ansible-playbook -i inventory/dev_env/hosts.yml playbooks/site.yml --tags audit_python_ca
```

Use `--limit <host>` for one server. A full site run includes the audit; when
selecting provisioning tags, also select `audit_python_ca` to include the check.
Place the audit after package updates and any venv recreation.

The role runs [files/audit.sh](files/audit.sh) using Bash and reports `changed=0`.
The script checks the Ubuntu CA package against
[USN-8944-1](https://ubuntu.com/security/notices/USN-8944-1), lists venv markers and
pip/certifi versions, and decodes named CA bundles under `/opt`, `/home`, `/root`
and standard Python library paths. It does not execute inspected venvs.

- `REVIEW`: outdated Ubuntu CA package or the removed emSign root is present.
- `SYSTEM-CA override`: recognizes Ubuntu's patched certifi and skips its unused
  bundled PEM. The system CA bundle is checked separately.
- `UNKNOWN`: an incomplete check, including an unsupported Ubuntu release.

Exit 1 means findings; exit 2 means incomplete checks. Both fail the playbook.
Old pip versions alone do not establish exposure when Ubuntu's system-CA patch
is present. A stored certificate finding requires review of whether it is used.
The audit does not prove credential theft or inspect containers, custom CA paths,
virtualenv seed archives, symlink-only trees or running processes.
