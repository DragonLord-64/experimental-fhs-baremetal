# Minimal, production-focused role cleanup and tests

## Objective and transfer

Clean up the official repository in this experimental repository first. Deliver
reliable, understandable Ansible roles, matching playbooks and concise docs for
user review and later transfer. The user will replace official `roles/`, `docs/`
and `playbooks/`, then initiate an official PR and review its details. Never push
or open a PR against official upstream from this task. Publish completed checked
work to the private experimental origin under the standing order.

Primary use: fresh Ubuntu servers (99%); secondary use: rerun a role for a small
configuration or package-version change (1%). Make these paths dependable. Avoid
new features, general migration/deletion frameworks, exhaustive edge-case handling,
large test infrastructure, broad refactors and cosmetic churn. Production readiness
is an objective, not a claim until supported by evidence; state hardware limits.

Start with current official fetch-only development2 (last reviewed 7704587),
record its SHA and align implementation deliberately while preserving accepted
experimental functionality and consolidated documentation. Keep diffs focused;
no mass formatting, gratuitous renaming or unrelated package upgrades.

## Execution and source boundaries

Work through roles one at a time with one implementation worker and the user's
review, not independent review agents. This combined task supersedes the queued
roles-upstream-alignment and grpc-role-coherence task scopes; retain those task
files as evidence and cancel their queued dispatches to avoid duplicate work.
NetBox JSON transfer and Nexus management-IP tasks remain separate and untouched.
No automatic dispatch of this large task until finite stages/checks are selected.

Transfer folders: roles/, docs/, playbooks/. Portable Molecule scenarios and their
small required fixtures may live with roles. All other lab orchestration,
containers, integration harnesses, captures and reports stay in ops/ or ignored
artifacts, outside transfer folders. Runtime source/docs must not depend on ops/.
Platform services belong in platform/, already a separately transferable source
boundary; explicitly list platform and necessary inventory changes as transfer
prerequisites rather than pretending the three folders alone contain everything.
Never copy protected inventory credentials or raw private captures.

## Agreed role changes

- setup_apt_source, setup_pip_source, setup_git_proxy: generally working; basic
  checks only. Ensure platform has apt-cacher-ng, persistent devpi and Squid Git
  proxy, taking design cues from /home/dragonlord/ska-mid-cbf-prototyping without
  copying blindly. Preserve working APT cache. Review access exposure, credentials,
  TLS and package verification; report concrete issues without feature expansion.
  Simple package fetch/install and Git fetch checks suffice. No elaborate outage
  matrices or proxy recovery framework. Prototype devpi uses 3141 and /var/devpi;
  Git reference k8s/k8s-git-proxy.yaml and src/git-proxy/.
- manage_users: solid; general cleanup and cross-role permissions only. Keep
  passwordless sudo for explicitly approved development users for now; production
  must not inherit developer access. Preserve other memberships. Resolve BittWare
  group identity/GID consistently (SDK currently requests 666), and refresh SSH
  membership after membership changes. Investigate, do not assume these explain
  every permission failure.
- manage_venvs: test standard Linux ownership/group permissions thoroughly with
  Molecule/Linux containers: allowed/denied access, intended-user package install
  and execution, unchanged rerun and permission drift. Check writable code versus
  privileged execution. No proprietary SDK required for these permission checks.
- manage_bittware_sdk: no proprietary SDK available. Use a minimal stand-in package
  for installer wiring, paths, users/groups and venv permissions. State explicitly
  that real installer, SDK commands and FPGA behavior are not validated.
- manage_gitlab-runner: keep runner account, its venv and per-user BittWare pip
  setup TOGETHER; do not move this into system SDK installation. Add configured
  BittWare supplementary membership without dropping existing memberships. Replace
  Python-3.12/pydantic-directory success sentinel with a meaningful installation
  check; verify with stand-in installer and fresh-session permissions. Do not add
  runner registration/installation functionality not requested.
- manage_dpdk_ark_doca: confirm existing unconditional purge/rebuild and make it
  conditional. Successful installation with unchanged inputs skips installation.
  Changed inputs rerun installation; changes needing a clean build delete/reinstall.
  Failed/incomplete installation reruns the FULL procedure, never piecemeal repair.
  Write success state only after full completion; track relevant source/settings
  simply and provide explicit force rebuild if needed. Define clean-build triggers.
  Basic setup tests with small fixtures; actual bundles/hardware remain separate.
  Align hugepage reservation/page size/mount with setup_fpga_host; review privileged
  execution of writable source. Do not silently ignore APT errors.
- setup_fhs_node: prepare to join only; NEVER execute kubeadm join. Validate/complete
  intended join preparation and configure labels and taints for later registration;
  affinity/tolerations belong to workloads. Review containerd config rewrite on
  every run, version compatibility with target cluster, ignored package-hold errors
  and mandatory Ceph assumptions. Do not automatically choose latest versions.
  Basic Molecule config checks; isolated VM for kernel/runtime behavior when needed.
  Do not create another Kubernetes cluster to avoid the existing fhs-test lab.
- manage_fhs_bist: basic installation placeholder, not production-ready application.
  Remove immediate trace-file/output check. Test installation/config only, not
  hardware results. Avoid expanding into BIST application development.
- ubuntu24_cis: keep external role; review selected policy, not wholesale hardening
  redesign. Ensure inventory/dev_env/group_vars/ubuntu24_cis_production.yml settings
  actually reach ALL intended Linux servers, not only fhs_nodes. Current group
  wiring appears missing and site overrides audit_only to false; enforcement is
  INTENTIONAL. Verify resolved vars before apply. Keep approved development sudo.
  Firewall assessment/configuration is explicitly OUT OF SCOPE; user owns it.
  Skip Chrony; network role must enable/run systemd-timesyncd using configured NTP.
  Review deferred patching/password-quality/AIDE controls with user, do not silently
  enable disruptive controls or pretend disabled controls prove deployed insecurity.
- manage_poetry/manage_fhs_grpc: absorb Poetry installation into gRPC, remove
  standalone site invocation and retire role after caller inspection. Keep all gRPC
  cleanup within this combined scope. NetBox tags grpc-fsp/grpc-vcc select ONE
  controller; neither skips, both fail before writes. Handle previous owned service
  on tag switch simply; no generic removal framework. Inspect actual inventory tag
  shape. Configurable per-controller device/card/region/port/bitstream settings.
  Use alternate package index and required dependency differences intentionally.
  Investigate whether fixing packaging in the controller dependency repos is the
  better solution; record recommendation, do not modify/push those repos without
  scope. Consider approved generated locks; never regenerate unconstrained locks
  every deployment. Compare upstream selected-release pyproject/lock/entrypoints
  to role templates; preserve necessary differences, document minimal overrides.
  Inspect pip versus Poetry index configuration, real FSP archive paths, PATH versus
  PYTHONPATH, runtime user/privileges, restart-on-failure and honest change reporting.
  No-change rerun must not reinstall/restart needlessly. Sources are official
  playbooks/development/update_repositories.yml controller GitLab project paths.
  Prior online raw-file fetch failed; upstream packaging analysis is still pending.
  Focused stand-in/emulation installation/service tests, no FPGA correctness checks.
- manage_fhs_exporter: use pinned real public source/package where accessible.
  Installation/config/permissions/service startup and reruns only; NO hardware
  readings validation, exporter correctness testing or simulated hardware probes.
  Remove unconditional forcereinstall, review dependencies and local Prometheus
  coupling, preserve working behavior.
- manage_prometheus: use pinned real downloaded Prometheus/Node Exporter binaries
  in shared exporter test environment where practical. Check install, config
  validation, rerun, version-change restart and service recovery. No monitoring
  feature expansion. Review authentication/permissions without firewall changes.
- filebeat: keep generally working device role. Preserve existing experimental
  tasks/setup.yml separation: delegate index-management setup to localhost once
  per play batch, separate setup/publishing credentials, same package, no local
  Filebeat daemon installation. Do not lose this during upstream alignment.
- setup_fpga_host: mostly works; minimal fixes backed by concrete problems. Review
  flags (site invocation alone doesn't enable firmware/GRUB), VFIO permissions,
  ignored udev errors and hugepage consistency with DPDK. Move rsync package/service
  tasks to end of site.yml, no new role. Do not run firmware or host reboot paths.
- setup_fhs_network: KEEP direct systemd-networkd, no Netplan migration. Write
  MAC-specific 00-fhs.network; preserve unrelated files, remove blanket deletion
  and catch-all ignore-others behavior. Verify first-match precedence. Retire only
  old role-owned conflicting files through a simple explicit transition. Validate
  required MAC/address/prefix before writes. Disable only cloud-init networking,
  not all cloud-init. Verify DNS/resolved behavior and timesyncd enabled/running
  with configured NTP. Actual internal NTP synchronization needs user validation.
  Use isolated VM for network application, preserve orchestration connectivity.

## Final consistency and documentation pass

After behavior fixes/tests: role-selection tags live in site.yml. Internal role
 tags only for explicit functional options or safety gates such as never/firmware.
Test tag inheritance and destructive opt-in; don't assume never is sufficient.
Unify variable naming only where it improves clarity; role-prefixed private settings,
explicit shared settings for common identities/indexes/NTP. Update callers and docs
 together; preserve compatibility where useful without elaborate alias machinery.
Keep one concise README per role included by Read the Docs. Actual commands/tags,
variables, prerequisites and limits; no generic tutorials. Inspect existing docs
voice and build required docs. Record focused evidence and source provenance.

## Acceptance and budget discipline

Before each bounded stage select finite exact checks; reuse existing Molecule and
helpers. A clean install, unchanged rerun and one relevant small-change/permission
check are normally enough. Use real services/binaries when available; test role
installation responsibilities rather than application correctness. Never build
large fake systems/full lifecycle matrices for small edits. Ordinary Molecule
scenarios may transfer upstream; all other test infrastructure stays experimental.
No test claims without observed results. Explain unavailable SDK/hardware/network
coverage. Validate changed runtime platform services on existing delivered-chart
fhs-test lab with explicit context; inspect services and follow WOL protocol.
Preserve user edits, data and credentials. Never reboot/shut down/suspend/hibernate/
halt/power off either host, including through role handlers. Do not run production
inventory, firmware operations or firewall work. No independent review agent.

Deliver a concise source-diff and validation summary, documentation build result,
known remaining limits and exact transfer prerequisites. Keep experimental workflow
files out of official copy. User performs detailed official PR review/transfer.
