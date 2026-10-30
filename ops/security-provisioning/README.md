# Security provisioning validation

Lab-only inventory mirrors deployment's `group_vars/all/`, device-role files and
resource subdirectories. It never invokes hardware provisioning. Values name the
existing dragonvm workspace; production uses its own resource root and endpoints.

```sh
# On dragonvm, after staging current roles/playbooks and private credentials:
cd /home/dragon-lord/fhs-security-20261030
ANSIBLE_ROLES_PATH=$PWD/roles ansible-playbook \
  -i inventory/hosts.yml playbooks/filebeat_setup.yml
```

Keep `resources/credentials/filebeat-setup.yml` private. The fixture expects the
selected `.deb` under `resources/external_archives/` and the public CA under
`resources/certificates/`. Setup uses the package temporarily; no controller
collector is installed. See [observed results](VALIDATION.md) and
[official transfer](TRANSFER.md).
