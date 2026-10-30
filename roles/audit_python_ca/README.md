# audit_python_ca

Read-only check for the October 2026 eMudhra/emSign certificate incident on Ubuntu
24.04. The certificate cleanup playbook runs it after cleanup; `site.yml` runs it
again after provisioning. It reports findings before failing;
it never updates certificates, removes venvs or installs packages.

Targets `device_roles_fpga-host-server`; use the current NetBox inventory.

```sh
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/audit_python_ca.yml --ask-vault-pass
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --tags audit_python_ca --ask-vault-pass
```

Use `--limit <host>` for one server. Both final checks carry `always` and
`audit_python_ca`, so tagged cleanup/provisioning runs still validate the host.
Use `--tags audit_python_ca` for validation alone. An intentional
`--skip-tags audit_python_ca` skips the final audit.

The role runs [files/audit.sh](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/roles/audit_python_ca/files/audit.sh) using Bash and reports `changed=0`.
The script checks the Ubuntu CA package against
[USN-8944-1](https://ubuntu.com/security/notices/USN-8944-1), lists venv markers and
pip/certifi versions, and decodes named CA bundles under `/opt`, `/home`, `/root`
and standard Python library paths. It does not execute inspected venvs.

The report starts with PASS, FAIL or INCOMPLETE and counts, followed by:

- `ACTION REQUIRED`: each finding gives the location, meaning and next step.
  pip findings concern package downloads; application certifi findings can remain
  after pip is patched. Seed-cache findings can affect future environment creation.
- `INCOMPLETE CHECKS`: unreadable bundles, discovery errors or unsupported OS
  validation prevent a pass and explain what needs investigation.
- `ENVIRONMENTS FOUND` and `PACKAGE VERSIONS`: inventory with environment paths
  instead of raw metadata filenames. Package versions alone are not verdicts.
- `SUCCESSFUL BUNDLE CHECKS`: `SYSTEM CA` recognizes Ubuntu's patched certifi and
  its unused bundled PEM; the system store is checked separately. `ROOT ABSENT`
  means the known removed root was not found in that decoded bundle.

Exit 1 means findings; exit 2 means incomplete checks. Both fail the playbook.
Old pip versions alone do not establish exposure when Ubuntu's system-CA patch
is present. A stored certificate finding requires review of whether it is used.
PASS means no known incident findings in the scanned locations. It does not prove
that every certificate on the host is safe or establish credential theft. The
audit does not inspect containers, custom CA paths, virtualenv wheel archives,
symlink-only trees or certificates loaded by running processes.
