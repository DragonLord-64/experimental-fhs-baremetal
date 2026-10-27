# Role cleanup — implementation evidence

## 2026-10-26 source baseline

- Start: `a5395d00715ee1a50454fc71e54820901580d7e7`.
- `git fetch upstream development2` succeeded; fetched source remains
  `7704587034e7e41f1b1266c109b0e903279617a9`.
- Upstream push URL remains `/dev/null`. No commit, push or deployment by worker.
- Initial working tree contains unrelated NetBox transfer/Nexus changes and log
  entries. Preserve these. Controller/queue files are outside worker authority.
- Compared transfer folders against upstream; retain consolidated role READMEs,
  Filebeat's delegated setup and existing experimental safety changes.

## Stage 1 checks selected before edits

The controller's source checker does not parse Ansible YAML or exercise Linux
permissions. Additional checks are necessary for those behaviors only:

1. `ansible-playbook -i localhost, ops/role-tests/cleanup/syntax.yml --syntax-check`
   with repository roles and pinned test collections.
2. Existing manage_users Molecule toolchain, extended with one permission/SDK
   stand-in scenario: `molecule test -s default`, bounded by `timeout 120s`.
   Verify fresh install, unchanged rerun, intended/denied user access, owner pip
   install/execution, preserved supplementary groups and permission drift repair.
   No privileged container, host mounts, hardware calls or host lifecycle changes.

Runtime source must remain independent of ops. Stand-in SDK only tests wiring;
real SDK installer, commands and FPGA behavior remain unvalidated.

First `timeout 120s molecule test -s default` returned 124 during idempotence,
after fresh convergence and verification. It exposed a real ordering problem:
SDK installation added files after venv permission repair, so the next venv run
changed permissions. Move permission application to a reusable role task file
and apply it after SDK installation. Owner package installation belongs in
convergence, not verification, so verification no longer modifies state.
For diagnosis, continue the existing owned container using separate bounded
`molecule converge`, `molecule idempotence`, `molecule verify`,
`molecule side-effect`, `molecule destroy` commands (each `timeout 120s`),
rather than rerunning package preparation or increasing the command budget.

Additional changed behavior: offline `ansible-playbook -i localhost,
ops/role-tests/cleanup/sudo-policy.yml` checks that default production policy has
no NOPASSWD and development opt-in names only approved key-file accounts. The
controller checker cannot resolve these Jinja variables. Existing Molecule sudo
policy fixture still validates an explicit override with visudo/sudo.

Observed after the ordering fix:

- Targeted four-role Ansible syntax: exit 0.
- `molecule converge`: exit 0, `ok=40 changed=0 failed=0` on the existing container.
- `molecule idempotence`: exit 0, `ok=40 changed=0 failed=0`.
- `molecule side-effect`: exit 0, `ok=96 changed=6 failed=0`; changed sudo
  policy, observed shell/key/sudo-mode and venv group/mode drift, repaired with
  actual roles and verified resulting state. Supplementary runner group retained.
- Offline production/development sudo-policy resolution: exit 0. First version
  failed because the block scalar overescaped the filename regex; corrected to
  `[.]pub$` and reran the failing assertions successfully.
- Logs are local `/tmp/fhs-role-cleanup-{molecule,converge,idempotence,drift}.log`.
  The first aggregate test timeout is retained; do not describe it as a full
  `molecule test` pass.

Final stage-1 checks selected after adding explicit approved-key-directory
validation and fixing the legacy manage_venvs scenario's missing role name:

- Repeat the targeted `syntax.yml --syntax-check` (new assertion/caller edit).
- `timeout 120s sphinx-build -b html docs/src /tmp/fhs-role-cleanup-docs`;
  changed role READMEs are included in Sphinx. This is a content/render check,
  outside the controller's source/link-only coverage. No warnings suppressed.

Prerequisite installation: repository-pinned Ansible/Molecule versions and
collections installed in `/tmp/fhs-role-cleanup-venv` and
`/tmp/fhs-role-cleanup-collections`. System Python lacked ensurepip; used
`pip --python /tmp/fhs-role-cleanup-venv/bin/python` instead of changing host
packages. Documentation theme was unavailable on PyPI; installing from the
project-declared SKA index succeeded. No host service or package changes.

Final focused verification: exit 0, `ok=8 changed=0 failed=0`, including group
write/execute access and unchanged root-owned 0755 system interpreter. Label-
checked `molecule destroy`: exit 0, removed only the test container.

## Stage 2 checks selected before edits

- Extend targeted Ansible syntax play with DPDK and FPGA roles; parse only.
- One small real Meson/Ninja C build fixture in an unprivileged container:
  fresh install, unchanged skip, changed archive and failed-install full rerun.
  Each Ansible command bounded to 120s. No DOCA/hardware bundle claims.
- Offline assertions on shared 1G hugepage count/size/mount and explicit firmware
  gates; never execute firmware, GRUB, mounts or host reboot operations.

Stage-2 offline render initially failed: actual `grub.j2` ignored
`fpga_kernel_cmdline` and hardcoded 16 pages. Changed it to render the configured
list (default 8 x 1G), then the render/contract check passed (exit 0).
The FPGA role's automatic reboot task was removed; udev reload now propagates
errors and firmware requires explicit `firmware` tag as well as its flag.

Further concrete stage-2 security correction: removed privileged `ninja uninstall`
from the old build tree, which the old role made user-writable. Do not execute
that historical build file as root. Clean source-tree deletion/reinstallation
remains; obsolete installed libraries are not generically pruned. Incremented
build revision to 2. Repeat the deliberate failure/default retry with final
revision-2 inputs so recovery evidence does not conflate a source change with
an absent success record. This extra check covers the changed build procedure.

Sphinx HTML build: exit 0, five warnings (one unavailable external Python
intersphinx inventory, four existing links to the external NetBox README).
These warnings were not suppressed or repaired as unrelated work. Rebuild HTML
once after stage-2 README changes with the same bounded command.

Public selected-release controller packaging is now fetched and inspected;
see [packaging evidence](PACKAGING.md). This supersedes the earlier raw-fetch
failure as an access limitation, but does not complete stage 4.

### Stage-2 observed results

- Six-role targeted Ansible syntax: exit 0, including final build procedure.
- Small real Meson/Ninja C project plus inert MFT/Arkville stand-ins:
  - Fresh installation: exit 0, `ok=35 changed=16 failed=0`.
  - Unchanged inputs: exit 0, `ok=9 changed=0 failed=0`, procedure skipped.
  - Changed DPDK archive: exit 0, `ok=37 changed=15 failed=0`, clean rebuild.
  - Deliberate final revision-2 installer failure: exit 2, installer rc 42,
    `ok=30 changed=11 failed=1`; success file absent afterward.
  - Same-input retry, no force flag: exit 0, `ok=35 changed=13 failed=0`;
    dependencies, DOCA, clean Arkville/DPDK trees, compilation, application
    installation and success record all ran, not a piecemeal repair.
  - Final unchanged rerun: exit 0, `ok=10 changed=0 failed=0`.
- Five full Arkville attempts observed (initial, source change, original failure,
  final-procedure failure, final retry); installed C fixture returned revision 2.
- Isolation observed: unprivileged, zero mounts, 512 MiB, one CPU, 128 PIDs.
- Final Sphinx HTML build exit 0, one warning for inaccessible external Python
  intersphinx inventory. Incremental build does not erase the four existing
  NetBox-link warnings from the initial full build.
- Reports: `/tmp/fhs-role-cleanup-dpdk-{first,unchanged,change,failure,final-failure,retry,final-unchanged}.log`,
  `/tmp/fhs-role-cleanup-docs{,-final}.log`. No deployment/hardware results.

## Incomplete overall scope / resume

Only stages 1–2 are implemented here; do not mark the six-stage objective ready.
Continue at stage 3, preserving these sources and the unrelated NetBox changes:

3. Node/network/CIS behavior, inventory group resolution and offline config tests.
   Current CIS policy lives under an unwired group; do not invent which unknown
   NetBox platform/role values represent all intended Linux servers. Establish
   sanitized inventory evidence/resolved vars before any application. No firewall
   work or join execution.
4. Poetry/gRPC/BIST implementation and stand-in service tests; real source
   inspection has started in PACKAGING.md, but bitstream layout remains pending.
5. Exporter/Prometheus/Filebeat real package/service/rerun checks.
6. Proxy platform changes, tag consistency, final docs and supervisor lab check.

No chart changes/deployment have been made. Supervisor owns future delivered-chart
Helm deployment and final runtime acceptance on existing explicit `fhs-test`;
this worker has not fulfilled those checks. Queue cancellation, controller state,
final acceptance command, commits and publication remain with the caller.

Current source transfer prerequisites:

- Transfer all six changed roles together: manage_users, manage_venvs,
  manage_bittware_sdk, manage_gitlab-runner, manage_dpdk_ark_doca, setup_fpga_host.
  The SDK role reuses manage_venvs/tasks/permissions.yml.
- Apply only the new development inventory settings (`fhs_keys_dir` and
  `fhs_development_passwordless_sudo`) deliberately; never copy protected
  inventory credentials. Production must supply an approved key directory and
  leave the development sudo option false. Shared group/GID defaults are
  bittware/666; existing filesystem GIDs still need review, not automatic migration.
- Supply approved SDK/DOCA/Arkville/DPDK artifacts. Stand-ins establish wiring
  and Linux permissions, not proprietary installers, drivers, hugepage boot
  behavior, SDK commands or FPGA/NIC correctness.
- Complete stages 3–6 before whole-task transfer. Platform services and necessary
  inventory changes are additional transfer prerequisites; three-folder copying
  alone does not install the still-pending proxy services.
- Keep ops/role-tests evidence/helpers out of official runtime folders. There is
  no runtime dependency from roles/docs/playbooks on these experimental helpers.

Cleanup completed: exact run-label checked before DPDK container removal;
subsequent label-filtered Docker queries found neither fixture container.
Controller acceptance command was not run. No agents, controller/run edits,
commits, pushes, deployments or host power operations were performed.

## Stage 3 checks selected before edits (2026-10-26)

Baseline against a5395d0: retained stages 1–2 and unrelated NetBox work; no
stage-3 changes initially. Source reviewed at upstream 7704587 remains evidence.
The controller source checker cannot execute Ansible/Jinja or resolve policy.
Run only these additional bounded checks (each timeout 120s):

1. `ansible-playbook -i localhost, ops/role-tests/cleanup/stage3-syntax.yml --syntax-check`
   with existing /tmp/fhs-role-cleanup-venv and collections; changed roles only.
2. `ansible-playbook -i localhost, -c local ops/role-tests/cleanup/stage3.yml`
   offline actual-template renders, preflight failures, network file preservation,
   cloud-init network-only disable, DNS/time service contracts, kubeadm labels/
   taints and no join, and actual effective CIS policy on node and non-node Linux
   fixtures. Files confined to /tmp; never run runtime roles against localhost.
3. `python3 ops/role-tests/cleanup/stage3_contract.py` for source safety/selection
   contracts and sanitized inventory membership; no private inventory output.
4. `sphinx-build -b html docs/src /tmp/fhs-role-cleanup-stage3-docs` for changed docs.

Availability check: local virsh, VBoxManage and /dev/kvm absent. Check existing
remote lab read-only for an already isolated guest; do not create VM/cluster,
apply networking/CIS or modify a host lifecycle. Runtime network/kernel behavior
is a limit unless a suitable existing isolated guest is actually identified.

Stage-3 implementation/diagnostic notes:

- Declared external CIS 1.6.0 fetched read-only to /tmp at
  `c893ca6836fb32b1ea067d4a63c341e39693074b`. Its enabled low-audit-space
  control otherwise renders `admin_space_left_action: halt`; override all four
  storage actions to syslog and assert effective safety policy before apply.
  Enforcement remains intentional; firewall section excluded, time owned by
  network role, patch/password-quality/AIDE deferrals unchanged for user review.
- SSH initially blocked by sandbox socket policy; read-only escalated connection
  succeeded. `virsh list --all --name` returned no guests. Existing explicit
  fhs-test node reports Kubernetes 1.37.1/containerd 2.3.4; service names inspected
  without mutation. No isolated network-test guest available. No WOL needed.
- First syntax run found a missing closing quote in the edited module loop;
  corrected. Next found missing community.general; fixed test environment with
  community.general 11.4.0 under /tmp (first automatic approval review timed out;
  allowed retry succeeded). No host package/service changes.
- Offline fixture initially hit read-only default Ansible remote temp; moved it
  to /tmp. Ansible correctly rejects loading handlers outside a runtime role.
  Use actual preflight task imports plus file task copies confined to /tmp,
  removing only root owner/group for this unprivileged file fixture and making
  the template source absolute. Runtime task ordering is separately asserted.
  No real role handler or host service runs; root ownership is source-checked,
  not claimed as runtime-validated here.
- Corrected fixture vars_files precedence and explicit Jinja evaluation of the
  actual containerd content scalar. Initial fixture failures were not passes.
  Python effective-vars helper uses Ansible's public trust_as_template API with
  repository-owned expressions (Ansible 2.20.1), not implicit string evaluation.
- Kubernetes runtime/API references inspected:
  https://kubernetes.io/docs/setup/production-environment/container-runtimes/
  and https://kubernetes.io/docs/reference/config-api/kubeadm-config.v1beta4/ .
  Generated-default cgroup settings support both containerd plugin layouts;
  exact runtime versions are required, no automatic latest selection. Current
  guidance removes containerd-1.x cgroup fallback in Kubernetes 1.38, not 1.37.

Final focused checks selected after correcting fixture evaluation and version
boundary: repeat stage3.yml and stage3_contract.py for these edits; add explicit
imports of both dynamically included node install task files to stage3-syntax.yml
so its parser covers actual package/runtime tasks. Also syntax-check changed
`playbooks/site.yml` (no execution, no live inventory). Repeat docs build only
because the runtime-boundary wording changed. All remain timeout 120s each.

### Stage-3 observed final results / handoff

- Changed-role syntax, including dynamic node package/runtime task files: exit 0.
- Changed `playbooks/site.yml` syntax: exit 0; localhost-only inventory naturally
  warns that fhs_nodes/ubuntu24_cis_production have no matching hosts. No run.
- Final offline `stage3.yml`: exit 0, `ok=62 changed=13 failed=0 rescued=5`.
  Four deliberate invalid network inputs and a mismatched cluster minor were
  rejected. No network files existed after invalid preflight. Actual rendered
  MAC/IP/DNS, cloud-init network-only YAML, taints/labels/CRI socket and configured
  NTP checked. Unrelated file preserved; old catch-all retired; Netplan preserved
  by default and removed only with explicit opt-in. File-only unchanged rerun
  reported all five applicable configuration tasks `ok` (no changes).
  Actual containerd content expression produced SystemdCgroup=true for 1.x/2.x
  layouts; repeat copies reported unchanged. Fixture files removed on success.
- Final `stage3_contract.py`: exit 0. Actual Ansible InventoryManager/VariableManager
  resolved production policy for compute, FHS-node and non-node control fixtures;
  switch excluded. NetBox role/tag and explicit Linux config-context selection
  checked. Source contracts checked service ownership, validation ordering,
  explicit cleanup gate, no join/reboot module and no ignored package errors.
  Existing hyphenated inventory group causes the expected group-name warning.
- Sphinx clean HTML build: exit 0, five warnings (external Python inventory
  unavailable and four existing external NetBox README links). Final incremental
  build after wording correction: exit 0, one external inventory warning; earlier
  link warnings remain recorded, not erased or suppressed.
- `git diff --check` for stage-3 paths: exit 0. Role includes and newly added
  inventory/site/evidence links point to existing files. Logs:
  `/tmp/fhs-stage3-offline.log`, `/tmp/fhs-stage3-docs{,-final}.log`.

Stage-3 changed paths: `roles/setup_fhs_node/`, `roles/setup_fhs_network/`,
`playbooks/site.yml`, new `playbooks/tasks/cis-policy-preflight.yml`,
`docs/src/playbooks/site.yml.md`, `inventory/README.md`,
`inventory/dev_env/{hosts.yml,netbox-inv.yml,group_vars/ubuntu24_cis_production.yml}`,
`ops/role-tests/cleanup/stage3*` plus this evidence and `wiki/LOG.md`.
No stage-1/2 or unrelated NetBox source edits were made by this continuation.

Transfer prerequisites: carry the sanitized explicit Linux policy group wiring
and selected CIS settings with the two roles and caller/preflight task; review
resolved membership so every intended Linux server is included. Unknown NetBox
roles are not guessed: mark their config context `fhs_linux_server: true` or merge
explicit linux_servers membership using the inventory directory. Supply reviewed
Kubernetes/control-plane/runtime versions, real package availability, network
MAC/address/prefix, authorized DNS/NTP and later discovery data. External CIS
1.6.0 and existing Goss/audit artifacts remain prerequisites. Do not copy private
inventory credentials or experimental ops helpers into transfer runtime folders.

Limits: no real CIS/network apply, runtime install/startup, kernel/sysctl/swap,
DNS reachability, internal NTP synchronization or join test. Root ownership in the
unprivileged offline network fixture is source-checked only. No hardware claim.
Live production NetBox inventory was not queried/applied. Existing fhs-test
versions were observed only; no cluster/VM/service changes. Supervisor owns
remaining runtime acceptance and later changed-chart deployment. Stage 3 is ready
for controller/human review; whole cleanup still requires stages 4–6. Controller
acceptance command was not run. No agents, controller/run changes, commits,
pushes, deployments, firmware or host power operations were performed.

## Stage 4 checks selected before edits (2026-10-26)

Scope only gRPC/Poetry/BIST and necessary callers/docs; preserve stages 1–3
and unrelated changes against a5395d0. No controller acceptance command.
Additional checks cover behavior the controller source checker cannot exercise:

1. `timeout 120s ansible-playbook -i localhost, ops/role-tests/cleanup/stage4-syntax.yml --syntax-check` (actual changed task imports).
2. `timeout 120s molecule <create|prepare|converge|idempotence|verify|side-effect|destroy> -s default`
   using one existing unprivileged Docker toolchain scenario, with stand-in
   controller packages and Poetry installer; check actual installation tasks,
   generated unit, fresh-user execution, unchanged rerun and controller switch.
   No systemd-capable isolated VM is available: record service-manager boundary
   explicitly rather than privilege a container or mutate host services.
3. `timeout 120s sphinx-build -b html docs/src /tmp/fhs-role-cleanup-stage4-docs`.
4. Changed-path `git diff --check` and affected local include/caller links.

Inspect local selected-release source and available bitstream source read-only;
no dependency repository edits. No application/hardware correctness assertions.

Stage-4 fixture diagnosis: first converge failed because fixture tarballs were
inside the container but unarchive intentionally reads controller-side archives.
Fetch fixture artifacts to a separate controller /tmp directory and rerun only
converge; do not change the role to accept a different production archive model.
Molecule create also ran prepare successfully within its 120s bound.
Second converge installed the real Poetry project successfully, then the service
stand-in failed because the unit's intentional runtime PATH excludes sbin and
the stand-in invoked runuser without its absolute path. Correct fixture to use
/usr/sbin/runuser. Reset only this container's fixture controller installation
and unit to obtain a clean installation result; retain toolchain and accounts.

First idempotence attempt correctly failed on service enablement: service-manager
stand-in misread systemctl's trailing `-l` as the unit name. Fix only its option
filter and repeat idempotence/verification; do not suppress changed results.
First Sphinx build exited 0 with seven warnings: five known external inventory/
NetBox references, plus two new README links to YAML not available as Sphinx
pages. Replace those two links with repository path literals and rebuild.
Real selected-release FSP and VCC `poetry check --lock` both exit 0 with pinned
Poetry 2.2.1 (SPDX/metadata/script deprecation warnings). This focused compatibility
check covers the newly preserved locks; no controller dependencies installed.
Split service transition and BIST fixture into separate bounded commands if
needed; both use the same owned container, without repeated preparation.

Additional bounded alternate-index check selected to cover the paired-override
branch (not covered by default-release convergence): prepare an empty-dependency
VCC fixture pyproject with an explicitly named primary PyPI mirror source and
matching fixture lock using real Poetry before deployment. Fetch the approved
pair, then `timeout 120s ansible-playbook -i /tmp/fhs-stage4-molecule/inventory
stage4-overrides.yml` from this cleanup directory. Assert one changed-input
restart and no repeat restart/install. This does not establish private mirror
availability or resolve real controller dependencies; deployment never locks.
Transition/BIST checks use the same inventory and `molecule/default/side_effect.yml`
with respectively `--skip-tags bist-fixture` and `--tags bist-fixture` to bound
the commands. No repeated preparation or new container.

### Stage-4 observed final results / handoff

- Changed-role syntax, including dynamic gRPC installation file and all BIST
  imports: exit 0. Caller YAML, README includes, retired role/caller references
  and no runtime dependency on ops checked; changed-path diff whitespace clean.
- Molecule create/prepare: exit 0, unprivileged Ubuntu container, no mounts,
  512 MiB, one CPU, 128 PIDs. Actual Poetry 2.2.1 installed, fixture-only locks
  generated before deployment. Public release lock compatibility checked without
  installing real controller dependencies (both exit 0; deprecations above).
- Clean controller install after fixture diagnostics: exit 0,
  `ok=27 changed=7 failed=0`. Toolchain/accounts retained from first attempt;
  selected controller installation/unit were reset, not the whole container.
- Molecule idempotence after fixture option correction: exit 0,
  `ok=23 changed=0 failed=0`. Molecule verify: exit 0,
  `ok=1 changed=0 failed=0`. Real fresh-user console process responds; BittWare
  supplementary group present, console executable accessible and code unwritable
  by runtime user. Its initial service-start count remained exactly one.
- Tag/transition play: exit 0, `ok=66 changed=8 failed=0 rescued=1`.
  Deliberate conflicting-tag assertion rescued and checked by exact task name;
  both invalid and empty selections created no target directory. FSP string tag
  switched to VCC dictionary tag; previous unit removed, process stopped and
  disabled; VCC console process responded. Same-input VCC rerun had no restart.
- BIST installation/configuration fixture: exit 0,
  `ok=12 changed=8 failed=0`. Empty reviewed requirements installed in real
  venv; actual directory/unit tasks ran. No BIST service-manager call or trace
  output, no pytest/hardware execution. Template discovery used an empty fixture
  directory; application templates/dependencies themselves are not validated.
- Approved alternate-source pair: exit 0, `ok=56 changed=5 failed=0` across
  changed-input installation and unchanged repeat. Real Poetry checked the
  fixture source/lock pair. Exactly one additional restart; subsequent repeat
  did not reinstall/restart. Separate direct socket assertion confirmed VCC
  console still responds after restart; retained in fixture for future runs.
- Sphinx clean HTML build: exit 0, seven warnings initially. Fixed two new YAML
  links; final incremental build exit 0, one external inventory warning. Four
  known external NetBox README link warnings from clean build remain recorded.
  No suppression or unrelated doc repair. Logs `/tmp/fhs-stage4-*.log`.

Stage-4 changed paths only: `roles/manage_fhs_grpc/`, retired
`roles/manage_poetry/`, `roles/manage_fhs_bist/{README.md,tasks/}`,
`playbooks/site.yml` (only standalone Poetry include removed in this stage),
`playbooks/archive/{install_grpc.yml,README.md}`,
`docs/src/roles/manage_poetry.md` (removed), `docs/src/playbooks/site.yml.md`,
`ops/role-tests/cleanup/{stage4*,molecule/,EVIDENCE.md,PACKAGING.md}` and
`wiki/LOG.md`. Prior stages and unrelated NetBox changes preserved.

Transfer stage-4 roles/callers/docs together, including role/document deletions.
Provide approved named controller/bitstream archives (including real driver
paths), Python venv support and shared bittware/666 identity. If alternate project
indexes are required, provide a reviewed matching per-controller pyproject/lock
pair: none for real controllers was invented or regenerated here. BIST archive
must contain pinned requirements.txt and its existing service account/group and
controller-side templates must be supplied; current vars/main.yml precedence is
explicitly documented. No stage-4 inventory/platform changes are required.

Limits: real systemd startup/recovery and real controller dependency installation
remain unvalidated; service-manager fixture launches real unprivileged stand-in
processes but is not systemd. No proprietary SDK, FPGA, actual driver/application
correctness, hardware probes or production application. Public bitstream tree
inspection is not proof of private downloaded archive contents. No new chart or
runtime platform source was changed in this stage. Full cleanup still awaits
stages 5–6, their platform/inventory transfer prerequisites, final documentation
pass and supervisor real fhs-test delivered-chart/runtime acceptance. Controller
acceptance command is reserved for caller. No agents, controller/run edits,
commits, push, deployments or host power operations.

Stage-4 cleanup: Molecule destroy exit 0 (`ok=3 changed=1 failed=0`), exact
ownership label checked before removing only `fhs-stage4-20261026`. Final
fixture Python/YAML parsing and changed-path `git diff --check` exit 0.

## Stage 5 checks selected before edits (2026-10-26)

Preserved stages 1–4 and unrelated changes against a5395d0. Scope only exporter,
Prometheus and Filebeat plus their documentation. Controller check is not run.
The source checker cannot exercise package installation, binary config validation
or service notifications. Select these additional checks, each timeout 120s:

- `ansible-playbook -i localhost, ops/role-tests/cleanup/stage5-syntax.yml --syntax-check`.
- One bounded unprivileged Ubuntu container using existing toolchain: real pinned
  exporter 0.0.5-rc3 archive, Prometheus 3.12.0 / Node Exporter 1.11.1 archives,
  Filebeat 9.5.5 deb where reachable. Targeted converge, unchanged repeat,
  binary-change notification and stopped-service recovery. No metrics requests,
  hardware collectors/probes, emulation or application correctness checks.
  Use existing minimal service fixture if systemd unavailable; report boundary.
- Real promtool config check, Filebeat test config and exporter console startup
  without a scrape. Preserve controller-only setup, separate credentials and
  same-package extraction. No live Elasticsearch setup claim without endpoint.
- `sphinx-build -b html docs/src /tmp/fhs-role-cleanup-stage5-docs` and changed-path
  `git diff --check`; documentation rendering is outside source checker coverage.

Public exporter source fetched at selected release 0.0.5-rc3 through GitLab API.
Sandbox DNS and Docker socket access failed; approved escalated read/fetch worked.
No existing isolated systemd VM identified by previous stage; no host mutation.

Container preparation initially failed: HTTP APT did not finish, HTTPS retry
reported missing CA roots in the minimal Ubuntu image. Copied the local public
CA bundle into the container (no verification bypass), retry with HTTPS/IPv4 and
15s acquisition timeout. No host package changes. Docker access requires tool
escalation in this sandbox. Systemd is installed only for unit/module interfaces;
PID1 remains sleep, so real systemd cannot be claimed.

First converge installed Prometheus/Node archives and validated generated config,
then failed: generic service dispatch rejected daemon_reload under container
service-manager detection. Use explicit systemd_service for these systemd units
(including exporter handlers), then repeat convergence without resetting packages.
Downloaded Prometheus, Node Exporter and Filebeat match published SHA256/SHA512
checksums. Container isolation: false privileged, zero mounts, 512MiB, 1 CPU,
128 PIDs. APT preparation succeeded after trust directory/bundle was present.

Concrete caller issue: update_repositories.yml downloaded the GitHub homepage
as monitoring tarballs and used versions different from role defaults. Corrected
only these two URLs/names to existing role pins, added published SHA256 checksums.
Syntax-check this changed caller too (no execution of its download playbook).
Prometheus 3.13.2 is a test-only second pinned binary for version transition.

Second convergence installed real exporter/imports but failed startup because
`lspci` was absent. Public selected-release source confirms its NIC constructor
calls lspci at startup (not only on scrape). Add the missing pciutils dependency;
sudo is also explicitly required by its ipmitool/MFT command paths. Do not mock
hardware commands or request metrics. Native PCI enumeration is an unavoidable
startup side effect, not a readings/correctness assertion. MFT remains unavailable
in test; none of its commands is exercised. Repeat only exporter convergence.
Split later role commands by fixture wrapper tags to keep each below 120s.

Existing focused Filebeat setup fixture selected for preserved delegation/auth
and cleanup coverage: `timeout 120s python3 -m unittest discover -s
ops/platform/logging -p test_role_setup.py -v` with existing Ansible on PATH.
It uses an inert package, not a live Elasticsearch API; real device package
installation/config/start is checked separately in the shared container.

Exporter continuation succeeded: ok=15 changed=2 failed=0, installed missing
pciutils then recovered stopped real exporter. Same archive skipped pip and
checksum writes. Default now dedicated root-owned fhs-exporter venv, keeping
privileged service code outside shared development-writable fhs venv. Existing
shared venvs are not deleted. Add private auth validation with real promtool
web-config and suppress auth template output/diff; recheck monitoring convergence.

Observed before transition checks:
- Final targeted three-role syntax and monitoring download-caller syntax: exit 0.
- Final Prometheus converge: exit 0, ok=17 changed=0 failed=0.
- Real Filebeat install/config/start: exit 0, ok=14 changed=6 failed=0; setup and
  output API checks deliberately disabled without live Elasticsearch.
- Existing Filebeat setup fixture: exit 0, one test passed (API-key success,
  password deliberate failure/cleanup, check-mode skip). No local daemon install.
- Real promtool config/rules and web-config checks, Filebeat config check, exporter
  help/import check, code/config ownership and actual process UID assertions pass.
  Initial starts exactly one each: Prometheus, Node, exporter, Filebeat.
- Sphinx clean HTML build: exit 0, five known warnings (external Python inventory,
  four external NetBox README links), no new warning suppression.

Remaining selected focused transition checks: per-role unchanged repeats; upgrade
Prometheus 3.12.0→3.13.2 and Node 1.11.1→1.12.1 using real archives, exactly one
restart each; repeat unchanged; stop all four fixture-managed processes and rerun
roles for bounded recovery. Also replace an installed binary at the SAME path
with the other real version, then rerun to prove archive-change notification
works even without a service-template change. Each role invocation timeout 120s.
No hardware readings/probes, metrics requests or real systemd assertions.

Privileged-code review: because exporter runs as root, add a pre-execution guard
rejecting existing venv files/directories writable by non-root (follow symlinks).
Do not silently take over an old shared venv recursively. Additional focused check
selected for this new behavior: make only the test console group-writable, run
exporter expecting the exact permission assertion before any console/pip/service
call, restore its mode, then use final recovery/rerun to validate repaired input.

Exporter pip replacement is conditional on changed archive/missing or broken
console. Within that branch force reinstall is intentional to replace SAME-version
archive contents and repair incomplete installations; unchanged runs never call
pip. Additional finite missing-console check selected for this repair branch:
`timeout 120s ansible-playbook -i /tmp/fhs-stage5-inventory
ops/role-tests/cleanup/stage5-permissions.yml`; same real pinned package, exactly
one exporter restart, no other service restarts. Also includes writable-console
rejection selected above. No fabricated hardware or package contents.

Selected-release exporter provenance: GitLab archive root identifies commit
`cd76705e08669ec620e7c9e949727ac52c33a807`, release 0.0.5-rc3;
archive SHA256 `4bdace55671ede497d6d07958c82b4002935d3719264cc28070a684e8c43288e`.
Both second-version binary archives also match published SHA256 sums.

Observed transition checks:
- Exporter/Filebeat unchanged run: exit 0, ok=26 changed=0 failed=0 (setup/output
  disabled as documented). All four start counts remained exactly one.
- Prometheus/Node version-change: exit 0, ok=19 changed=6 failed=0; real versions
  confirmed 3.13.2/1.12.1, counts exactly two each, other services unchanged.
- Same upgraded inputs: exit 0, ok=17 changed=0 failed=0; counts unchanged.
- Replaced both installed binaries at the same paths with older REAL versions.
  Rerun restored selected archives: exit 0, ok=19 changed=4 failed=0; unit templates
  unchanged, archive notifications restarted each exactly once (counts three).
- Permission/incomplete-install play: exit 0, ok=33 changed=5 failed=0 rescued=1.
  Exact writable-code assertion rejected group-writable console before executing
  it; no start counts changed. Restored mode, deleted console; real same-version
  package repair ran and restarted ONLY exporter once (count two).
- Final syntax after guard/conditional repair edit: exit 0. Final incremental
  Sphinx: exit 0, one external inventory warning; initial four NetBox warnings
  remain recorded, not erased by incremental build. Helper Python/YAML parse and
  focused diff whitespace check passed. No whole/controller acceptance run.

Stage-5 exposure/dependency review (no firewall work): Prometheus and Node listen
on all addresses, auth off by default; enabling Prometheus auth now requires a
private hash and actual promtool web-config validation. No TLS listener is added;
provide approved TLS termination/access controls. Exporter also binds all
addresses, has no auth, and retains root for SDK/MFT/IPMI; default isolated venv
and pre-execution write guard protect its code. Supply approved SDK commands on
PATH and MFT package source. Python transitive dependency versions follow the
selected public archive's declarations and the configured pip index; Poetry
source settings do not configure pip. Filebeat's existing default HTTP endpoint
would expose publishing/setup authentication on the network; supply HTTPS/CA
settings for production. Existing endpoint and credential separation preserved.
No hardware readings, firewall changes or upstream application edits were made.

Stage-5 invocation environment (existing toolchain, disposable inventory only):

```bash
export PATH=/tmp/fhs-role-cleanup-venv/bin:$PATH
export ANSIBLE_ROLES_PATH="$PWD/roles"
export ANSIBLE_COLLECTIONS_PATH=/tmp/fhs-role-cleanup-collections
export ANSIBLE_LOCAL_TEMP=/tmp/fhs-stage5-ansible
# Each invocation was independently bounded, with output under /tmp/fhs-stage5-*.log.
timeout 120s ansible-playbook -i /tmp/fhs-stage5-inventory ops/role-tests/cleanup/stage5.yml --tags manage_prometheus
timeout 120s ansible-playbook -i /tmp/fhs-stage5-inventory ops/role-tests/cleanup/stage5.yml --tags manage_fhs_exporter,filebeat
timeout 120s ansible-playbook -i /tmp/fhs-stage5-inventory ops/role-tests/cleanup/stage5.yml --tags manage_prometheus -e manage_prometheus_prometheus_tar=prometheus-3.13.2.linux-amd64 -e manage_prometheus_node_tar=node_exporter-1.12.1.linux-amd64
timeout 120s ansible-playbook -i /tmp/fhs-stage5-inventory ops/role-tests/cleanup/stage5-permissions.yml
```

Nonportable test service/verification helpers stay in ops/role-tests/cleanup.
They must never be installed on actual hosts. Container service fixture launches
real unit commands, with Prometheus using an empty scrape config to avoid ALL
exporter metrics/collector execution; deployed Prometheus config/rules are checked
separately with real promtool. Filebeat process runs against an unused loopback
endpoint, with no real publishing/setup credentials. No live API acceptance.

### Stage-5 final result and transfer handoff

- Bounded stopped-process recovery: monitoring play exit 0, ok=17 changed=2;
  exporter/Filebeat play exit 0, ok=28 changed=2; no package or config changes.
  Actual process/config/UID checks passed afterward. Counts exactly one higher
  per stopped service: Prometheus=4, Node=4, exporter=3, Filebeat=2. This proves
  role rerun recovery in the fixture, not systemd automatic restart or boot.
- Ownership label verified as fhs-stage5-20261026; removed only that container.
  Label-filtered query empty afterward. No host package/service changes.
- Stage-5 changed sources: roles/manage_fhs_exporter/{tasks,defaults,handlers,
  meta,README.md}, roles/manage_prometheus/{tasks,defaults,handlers,templates,
  README.md}, roles/filebeat/README.md, playbooks/development/update_repositories.yml.
  New stage5* helpers/evidence stay in ops/role-tests/cleanup; wiki/LOG.md updated.
  All previous stages and unrelated NetBox/controller/run files preserved.
- Transfer these role/caller changes together; existing docs includes already
  consume the concise role READMEs. Supply reviewed controller-local archives
  matching pins, approved MFT/SDK installation and root-owned exporter code.
  Review any inventory override of old shared fhs_exporter_venv_path explicitly;
  default is now /opt/venvs/fhs-exporter. Supply private auth hashes and HTTPS/CA
  endpoints as appropriate. No new inventory/platform source is required by
  THIS stage. Overall transfer still needs stage-6 platform/inventory prerequisites.
- Ready means stage-5 implementation/nondeployment checks only. Stage 6 proxy,
  final consistency and supervisor actual delivered-chart acceptance on existing
  explicit fhs-test remain. Real systemd sandbox/restart/boot, live Elasticsearch
  setup/publishing/journal ingestion, MFT/SDK/hardware and readings correctness
  remain unvalidated. No metrics probes/emulation/simulated hardware were used.
- Controller acceptance command remains for caller. No agents, controller/run
  modifications, commits, pushes, deployment or host power operations.

## Stage 6 checks selected before edits (2026-10-26)

Scope: proxy chart sources, remaining role selection tags/callers and concise
transfer documentation only. Preserve all prior stages and unrelated NetBox work.
Additional checks cover Helm, Ansible selection, real proxy processes and Sphinx,
which the controller's reserved source/link check cannot exercise. Each command
is bounded to 120 seconds; no chart deployment or host service changes:

- `timeout 120s helm lint platform/charts/fhs-platform --namespace hw-management`
- `timeout 120s helm template mid-cbf-hw platform/charts/fhs-platform --namespace hw-management > /tmp/fhs-stage6-render.yaml` (never print rendered Secrets).
- `timeout 120s python3 ops/role-tests/cleanup/stage6_contract.py` on rendered
  proxy config/services/PVC/security and offline actual Ansible selection.
- Existing Ansible toolchain: syntax-check site/provision and changed role task
  imports; list-tags/list-tasks and safe stand-in action selection for firmware
  default, role-only and explicit opt-in. No firmware task execution.
- Disposable unprivileged Docker processes using the exact pinned images and
  rendered commands/config: devpi initialization/cache pip install, Squid config
  parse and public Git fetch, APT basic package fetch if practical. No outages,
  hardware probes, host mounts, host networking or new test framework.
- `timeout 120s sphinx-build -b html docs/src /tmp/fhs-role-cleanup-stage6-docs`.
- Focused `git diff --check`; source/link acceptance remains controller-owned.

Prototype inspected: images/ska-mid-cbf-devpi/{Dockerfile,entrypoint.sh},
src/devpi/entrypoint.sh, k8s/k8s-git-proxy.yaml and src/git-proxy/ under
/home/dragonlord/ska-mid-cbf-prototyping. Retain devpi 3141 + /var/devpi;
replace unpinned build dependency with reviewed prebuilt image. Git proxy uses
3128 and allowlisted destinations; tighten method/port ordering and avoid disk
cache/TLS interception. Existing pinned APT chart/cache remains unchanged.

### Stage-6 observed results and final source handoff

- Inspected baseline diff against a5395d0; stages 1–5 and unrelated NetBox/Nexus
  edits preserved. Local official ref is still 7704587034e7e41f1b1266c109b0e903279617a9
  from the successful stage-1 fetch. No new upstream fetch claim in this stage.
- Public image source reviewed at
  https://github.com/JonasAlfredsson/docker-devpi (server Dockerfile/entrypoint)
  and https://hub.docker.com/r/ubuntu/squid . Registry manifests resolved and
  pulled by digest; actual image versions devpi 6.20.3 and Squid 6.13 (despite
  the Canonical 6.6-24.04_beta channel name). No build/startup pip requirement.
- Helm lint: exit 0; one chart linted, zero failed. Existing Grafana probe
  coalescing warnings and optional icon recommendation remain. Initial/default
  and final post-memory-fix Helm template: exit 0; renders only under /tmp,
  never printed because they contain generated Secrets.
- Targeted distribution/users/SDK/FPGA role syntax: exit 0. Site/provision syntax:
  exit 0 with expected empty localhost inventory group warnings. Actual site
  --list-tags and role-selected --list-tasks: exit 0. Dynamic includes' internal
  tasks are not enumerated by those commands.
- Focused final rendered contracts and actual-main inert Ansible selection:
  exit 0. New services are ClusterIP by default, exact ports/images, no service
  account tokens, non-root new containers, retained devpi claim/Recreate strategy,
  deny-before-allow Git ACLs. Firmware cases: unrestricted + flag true skips;
  role-only + flag true skips; explicit firmware + flag false skips; explicit
  role/firmware + flag true selects inert marker. Udev marker selected in all
  four, GRUB marker absent with default false. No real firmware/udev/GRUB action.
- Disposable devpi initially OOM-killed at 512Mi while creating its server
  secret; diagnosed OOMKilled=true, increased container/chart limit to 1Gi.
  Final process running, OOMKilled=false; /+status HTTP 200. Earlier diagnostic
  attempted JSON without Accept header and failed parsing HTML; not a server
  failure. Real six==1.17.0 pip install through /root/pypi/+simple succeeded,
  imported version confirmed. No admin password was logged/exposed; cache-only
  initialization uses an unrecorded random root password, modification root-only.
- Actual rendered Squid config parsed successfully under image UID/GID 13 with
  all capabilities dropped. Real gitlab-org/cli ref listing and shallow Git
  object fetch passed through proxy; FETCH_HEAD
  a6eb09b6da1f05c423201a690876ae5e602abab6. Unlisted example.com CONNECT denied.
  No TLS interception, disk cache or HTTP credential was used.
- Unchanged APT image/basic fetch: initial fixture lacked chart cache/log mounts
  and failed log-file permissions. Recreated ONLY that labelled fixture with
  corresponding disposable mounts; exact existing rendered config/command
  fetched hello_2.10-3_amd64.deb (53080 bytes), dpkg-deb identified hello 2.10-3.
  This is transport/package-structure evidence, not an apt signature/install
  result. Existing APT chart sources/PVC/config were not changed.
- All daemon fixtures unprivileged, no host binds/published ports, 1 CPU and
  128 PIDs; devpi 1Gi, Squid/APT 256Mi. Devpi data was tmpfs for isolation;
  this is NOT a Kubernetes PVC/persistence result. Client used existing public
  devcontainer image; no host packages/services modified.
- Sphinx clean HTML: exit 0, five known warnings (external Python inventory
  unavailable, four existing external NetBox README links). No new warnings
  suppressed. Focused changed-path git diff --check: exit 0.
- Source changes for this stage: platform chart values/schema and four proxy
  templates plus README/CONFIGURATION; remove generic internal selection tags
  in manage_users/manage_bittware_sdk/distribution tasks, keep FPGA functional/
  safety options; add upstream rsync package/service tasks at end of site;
  update role/site/playbooks docs. No variable renames or new inventory endpoints.
  Prior-stage facts and hardware/systemd/network/CIS limits still apply.

Final supervisor commands, role source-diff table and exact platform/inventory/
caller transfer prerequisites: [STAGE6-HANDOFF.md](STAGE6-HANDOFF.md). All source
stages are now ready for controller/human review, not whole-task completion.
Supervisor owns actual existing fhs-test delivered-chart deployment, Service/PVC
and basic fetch acceptance; do not substitute these Docker tests for that step.
Controller owns reserved checks.py, queue cancellations and publication. No
agents, controller/run edits, commits, pushes, deployments, host service/firewall
changes or host power/firmware operations by this worker.

Final post-memory-change Helm lint: exit 0, zero failed charts; same existing
Grafana probe warnings. Final focused whitespace check exit 0. Cleanup verified
each exact stage6-20261026 ownership label before removing the three disposable
containers; matching Docker label query empty afterward. No acceptance command
was run. Local reports remain under /tmp/fhs-stage6-*.


## Final supervisor runtime acceptance — 2026-10-26

Existing dragonvm fhs-test release/namespace fhs-inventory-alignment inspected
first. All original pods/PVCs were Ready/Bound. Private release values, manifest
and original resource identities saved under
`/home/dragon-lord/fhs-role-cleanup-20261026/` (mode0600 evidence; not committed).
The existing-style post-renderer was extended to keep NetBox/backing services
and add ONLY APT/devpi/Squid. New cache claims use inspected dynamic `standard`
storage; retained original claims keep fhs-retain and their identities.

Actual `helm upgrade` against the delivered chart passed: revision5 installed
proxies, revision6 applied the cache-only correction below. All three proxy
Deployments available, both new1Gi cache claims Bound. Original pod/PVC UIDs and
pod restart counts unchanged, including NetBox web/worker. No production systems.

Actual live finding/correction: the devpi image enabled full-PyPI web-search
indexing although this service is cache-only. Its installed null backend was
verified; startup now uses `--indexer-backend null`. Helm lint/template and
`stage6_contract.py` passed after the correction. The first contract invocation
lacked the temporary Ansible PATH; rerun with the documented toolchain passed.
The corrected chart rolled out successfully on the same initialized cache.

A single disposable Ubuntu client pod used Service DNS, not port-forward:
- APT cache supplied package metadata and installed Git/Python client tools.
- pip installed/imported six1.17.0 through devpi.
- Git fetched real GitLab objects through Squid with certificate verification.
- Squid rejected unapproved CONNECT destination403; devpi rejected unauthenticated
  index creation. Initial Python CONNECT-denial assertion expected HTTPError;
  corrected expected URLError403 and reran successfully. No unauthorized write.
- One devpi-only restart preserved initialized state, an acceptance marker and
  cached six wheel. A second pip installation/import through Service DNS passed.
- All three proxies available afterward. The client pod was label-checked and
  removed; retained chart services/caches remain available for user review.

Private observed summary: `acceptance-summary.json` in that directory; helper
scripts and private Helm logs remain outside transfer folders. No raw credentials
or inventory captures committed. Source/controller checks and docs results from
the six stages remain above; no whole lifecycle or hardware suites added.

Remaining validation limits: real systemd/boot/kernel/network/CIS application,
internal DNS/NTP reachability, real controller dependency installation, live
Elasticsearch publishing, proprietary SDK/FPGA/physical switch behavior. These
limits do not imply failed role tests or established production readiness.

Final supervisor source verification: `python3 ops/agent-pipeline/checks.py`
passed27 source/link checks after the cache-only startup/evidence changes.
Because the default command only discovers tracked changes, also inspected the
55 new task-owned files (excluding pre-existing user handoff/emulator files)
through that same check module:18 additional source/link checks, zero failures.
Final `git diff --check` passed. Disposable proxy client deletion completed.
All agreed source stages and scoped live chart acceptance are complete for user
review; the original stopped pipeline attempts remain historical evidence, and
no implementation worker remains active. Publication belongs to the caller.
