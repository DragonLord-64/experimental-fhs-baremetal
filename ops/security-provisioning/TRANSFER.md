# Provisioning/security transfer — 2026-10-30

Official comparison: `development2` at `2638d5bd1533654bb8edb750fe29e4f4fb47c3b1`,
confirmed remotely on 2026-10-30. Official already contains the APT/devpi/Git
services and client roles. This update configures the new deployment, trusted
HTTPS and portable inventory; it does not require importing the old proxy images.

## Copy source

With the checkouts beside each other, run from experimental:

```sh
python3 ops/security-provisioning/copy-to-official.py
git -C ../ska-mid-cbf-fhs-baremetal status --short
git -C ../ska-mid-cbf-fhs-baremetal diff
```

Pass a destination path if its folder has another name. The script copies the
listed source folders/files and overwrites matching files. It does not use Git,
merge settings or create backups. After copying, it removes the obsolete
`roles/setup_fhs_node/` directory and `docs/src/roles/setup_fhs_node.md` if present;
the replacement is `setup_k8s_node`. Other destination files are retained. NetBox inventory is
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
2. Edit `platform/values-provisioning.yaml` for storage, ingress class, DNS and
   TLS Secret names. Dedicated devpi/Elasticsearch hostnames are proposed and
   require DNS records pointing at ingress, plus site-issued certificates.
3. Create TLS Secrets in `hw-management`; install public CA trust on the
   provisioning host/container before loading NetBox inventory. Set
   `platform_ca_certificates` to distribute the public CA to managed servers.
4. Put the selected Filebeat `.deb` and other reviewed artifacts in the resource
   directory mounted at `/provision/files.d`. Supply separate Vault-capable
   `credentials/filebeat-setup.yml` and `credentials/filebeat.yml`; the latter
   matches the platform publisher password. No role retrieves cluster Secrets.
5. Install/upgrade the platform with the site values. Confirm the new APT/Git
   service DNS names resolve to reachable LoadBalancer addresses, and that devpi,
   NetBox and Elasticsearch HTTPS verify from the controller and targets.
6. Run Filebeat setup explicitly using `playbooks/filebeat_setup.yml`, then
   provision selected device-role hosts. Setup extracts the same package without
   installing a controller service. Device log collection is a separate role run.

Use the commands in [inventory usage](../../inventory/README.md),
[platform installation](../../platform/charts/fhs-platform/README.md) and
[Filebeat usage](../../roles/filebeat/README.md).

The newer certificate cleanup/audit and gRPC retirement are also pending official
transfer. Cleanup removes the selected legacy controller/provisioning environments;
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

The old `manage_venvs`, `manage_bittware_sdk` and `manage_gitlab-runner` entry
points now stop with migration instructions. Copy their replacement main task
files too; the plain-copy script leaves any obsolete files on disk, but those
entry points no longer run duplicate implementations. The optional
`playbooks/preflight.yml` command is documented in
[preflight usage](../../docs/src/playbooks/preflight.md).
