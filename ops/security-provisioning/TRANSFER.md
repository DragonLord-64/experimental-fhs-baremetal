# Provisioning/security transfer — 2026-10-30

Official comparison: `development2` at `2638d5bd1533654bb8edb750fe29e4f4fb47c3b1`,
confirmed remotely on 2026-10-30. Official already contains the APT/devpi/Git
services and client roles. This update configures the new deployment, trusted
development HTTP and portable inventory; it does not require importing the old proxy images.

## Copy source

For the full provisioning/security transfer, with checkouts beside each other,
run from experimental:

```sh
python3 ops/security-provisioning/copy-to-official.py --full
git -C ../ska-mid-cbf-fhs-baremetal status --short
git -C ../ska-mid-cbf-fhs-baremetal diff
```

For the current hardware-management workflow only:

```sh
python3 ops/security-provisioning/copy-to-official.py
```

The default copies the `hwmanage` executable/package, portable Bifrost templates,
native NetBox playbooks and their dependencies, the affected provisioning entry
points and their exact usage pages. It does not copy roles, inventory/group vars,
platform values or credentials, and performs no cleanup deletions. Matching files
are overwritten; unrelated destination files are retained. Review the explicit
manifest in [copy-to-official.py](copy-to-official.py) and the official Git diff.
This is a file copy, not a merge or a deployment.

For only the wrapper/import diagnostics update on an existing hwmanage checkout:

```sh
python3 ops/security-provisioning/copy-to-official.py --diagnostics-only
```

This copies the command runner, CLI, NetBox connection/credential loaders,
standalone Ironic importer, import playbook and usage page. The default and full scopes also include these files.

For only the six Bifrost environment repair/build files:

```sh
python3 ops/security-provisioning/copy-to-official.py --bifrost-only
```

That scope copies the patch script, launcher script, Bifrost Dockerfile,
constraints helper, operations guide and quickstart. The patch helper's
`configure` action supplies configuration-only guards without overwriting your
mounted `target` variables.

Pass a destination path if its folder has another name. With `--full`, the script copies the
listed source folders/files and overwrites matching files. It does not use Git,
merge settings or create backups. After copying, it removes the obsolete
`roles/setup_fhs_node/`, `roles/manage_venvs/`, `roles/manage_bittware_sdk/` and
`roles/manage_gitlab-runner/` directories and their role documentation pages if
present. Their replacements are `setup_k8s_node` and `manage_users`.
It also removes the eight obsolete standalone platform values files
(`elasticsearch`, `grafana`, `kibana`, `netbox-postgresql`, `netbox-valkey`,
`netbox`, `prometheus`, `telegraf`, all `.yaml`). Other destination files are retained.
NetBox inventory is
copied verbatim; review its token and site settings in Git. Host inventory and
host vars are not copied. Remove obsolete files listed below manually.

Review changes in a clean official checkout, preserving destination credentials
and deployment overrides. Copy these source directories together, including new
files and reviewed deletions:

- `roles/`, `playbooks/`, `platform/`, `docs/src/`.
- `inventory/README.md` and the two new group-vars directories under
  `inventory/dev_env/group_vars/`.
- Root `ansible.cfg`: its default inventory now selects the NetBox plugin
  directly instead of merging the old host snapshot.

Remove the old `group_vars/all.yml` and
`group_vars/device_roles_fpga-host-server.yml` after installing their replacement
directories. Merge `inventory/dev_env/netbox-inv.yml`: use the new deployment URL
and certificate verification, but supply the new NetBox token privately. Preserve
the actual host vars and reviewed CIS group/policy files. Do not replace current
NetBox hosts with the old `hosts.yml` snapshot.

Keep official root CI settings. The retained
`platform/charts/deploy_upgrage_mid-cbf-hw.sh` helper now loads the provisioning
values and accepts additional Helm arguments for private overrides.
Official Kubernetes/containerd pins and the explicit downgrade opt-in are
preserved in the split runtime settings. BIST remains installation-only and
enabled as previously agreed; Filebeat setup failures are no longer ignored.
The deleted duplicate `playbooks/playbooks/` READMEs stay deleted. Do not copy
`ops/`, `wiki/`, `examples/`, private instructions, raw captures, lab certificates,
or the untracked session handoff. Never copy `.git/` or experimental Git history.

## Supply site inputs

1. Review split connection/identity group vars; existing development sudo and
   account settings are not automatic production policy.
2. Review `platform/values-provisioning.yaml` for storage, the existing platform
   hostname and LoadBalancer service types. Internal development endpoints use
   HTTP; no additional DNS names, TLS Secrets or internal CA installation are
   required. HTTPS may be configured later.
3. After Helm installation, run `python3 platform/charts/export-platform.py`
   on the cluster host. Copy `platform-secrets.yml` to the controller resource
   mount's `credentials/` directory and `platform-endpoints.yml` to its root.
   Encrypt the whole secrets file using Vault. Copy only the exported `netbox_url`
   into the inventory plugin's `api_endpoint`; its token lookup reads the shared file.
4. Put Filebeat and the other configured archives under `external_archives/`.
   Generated platform secrets contain separate setup/publishing identities;
   no platform password needs to be assembled by hand.
5. Install/upgrade the platform with the site values. Confirm the new APT/Git
   service DNS names resolve to reachable LoadBalancer addresses, and that devpi,
   NetBox, devpi and Elasticsearch HTTP endpoints are reachable from their clients.
6. Run Filebeat setup explicitly using `playbooks/filebeat_setup.yml`, then
   provision selected device-role hosts. Setup extracts the same package without
   installing a controller service. Device log collection is a separate role run.

Use the commands in [inventory usage](../../inventory/README.md),
[platform installation](../../platform/charts/fhs-platform/README.md) and
[Filebeat usage](../../roles/filebeat/README.md).

The one-off certificate cleanup/audit is also pending official transfer. Cleanup removes the selected legacy controller/provisioning environments;
follow [its tagged commands](../../docs/src/playbooks/certificate-update.md).
This pass does not change throughput limits or tune production resources.

Accounts and BittWare environments now use one `manage_users` role/tag. Copy its
new task files, `playbooks/site.yml` and environment group vars together. The
`gitlab-runner` account is an entry in `fhs_users`; the separate venv/SDK/runner
tags are no longer selected by `site.yml`. See [user setup](../../roles/manage_users/README.md).

## Validation

Lab commands/results live beside this note, outside copied source. Lab success
does not establish production DNS, certificate issuance, credentials, hardware
behavior or a completed official deployment.

Account, SDK and environment setup use `manage_users`. The obsolete standalone
roles and their documentation pages are deleted by the copy script. The optional
`playbooks/preflight.yml` command is documented in
[preflight usage](../../docs/src/playbooks/preflight.md).
