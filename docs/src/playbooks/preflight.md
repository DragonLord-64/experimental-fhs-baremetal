# Provisioning preflight

Check selected inputs before provisioning. This command reads configuration,
files and endpoint responses; it does not install packages, create accounts,
configure services or run Filebeat setup.

```bash
# Default: distribution access plus user/SDK inputs on selected servers.
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/preflight.yml --limit <HOST> --ask-vault-pass
# Check only Filebeat setup inputs and controller-to-Elasticsearch HTTPS.
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/preflight.yml --limit <HOST> --ask-vault-pass -e '{"preflight_checks":["filebeat_setup"]}'
```

Select one or more names in `preflight_checks`:

| Check | What it reads |
|---|---|
| `distribution` | pip settings, controller CA source files, APT/Git proxy TCP listeners and pip HTTPS from the target |
| `users` | Approved public-key directory, account inputs and the selected SDK archive/header or existing target installer |
| `filebeat_setup` | Controller package and setup credential fields, delegate CA files and Elasticsearch HTTPS from the setup delegate |
| `filebeat` | Controller package and publishing credential fields, target CA files and Elasticsearch HTTPS from the target |

Use the same host limit as the provisioning command so its group/host vars apply.
Filebeat credentials support Ansible Vault; their contents are suppressed in
output. Public CA files and artifacts must be readable by the provisioning user.

For new hosts whose CA trust or endpoints are not ready, check inputs only:

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/preflight.yml --limit <HOST> --ask-vault-pass -e preflight_check_endpoints=false
```

This skips network probes and client CA-file checks. Then configure
distribution/CA access and rerun without that override. Network
checks default to a ten-second timeout; change `preflight_timeout` if needed.
NetBox inventory loads before this playbook starts, so its controller CA trust
and API token must already work.

HTTPS checks verify the certificate and hostname, including configured CA
bundles. A 401/403 confirms a reachable authenticated endpoint; it does not prove
credential validity or privileges. APT/Git checks confirm TCP reachability, not
package signatures, proxy allowlists or successful downloads. Preflight does not
replace each role's validation or guarantee a full provisioning run will succeed.

After a pass, run the required [site role](site.yml.md) or
[Filebeat setup command](../roles/filebeat.md).
