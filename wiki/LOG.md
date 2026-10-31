# Dated log

Append completed events here; keep proposed work in the plan.

## 2026-10-21

- Inspected the source checkout, pipeline, monitoring documentation, and development server capacity.
- Created a separate experimental clone and private GitHub repository.
- Original-history upload was rejected by GitHub for historical files exceeding 100 MB. Preserved full local Git history separately and prepared a current-tree snapshot import.
- Added the environment plan, agent instructions, and initial knowledge wiki. No test infrastructure has been deployed.
- Published the snapshot and initial wiki to the private GitHub repository.
- Documented the proposed controller resource layout and NetBox ownership boundaries; no inventory migration performed.

- Added the local agent pipeline under `ops/agent-pipeline/`: fresh screening/tests, implementation and read-only review processes, bounded retries, explicit verification commands, JSON status, logs and tmux monitoring. Eleven fake-executable integration tests verify transitions, interruption, verification visibility and cancellation without model calls. A real tmux monitor smoke test passed. Independent review findings were corrected; real authenticated dispatch remains unverified.
- Tested the controller on `dragonvm`: all eleven fake-agent tests and live tmux/intervention checks passed. Real Codex smoke attempts correctly stopped as blocked because both configured and built-in default models were rejected by the remote ChatGPT account; see `ops/agent-pipeline/VALIDATION.md`.

- Diagnosed dragonvm’s real Codex blocker as noninteractive SSH selecting the old system CLI. Pinned the updated user executable for an isolated bounded smoke, retaining `gpt-6.1-sol`. Three fresh pipeline workers completed screening, implementation and independent review; exact file content and all eleven controller tests passed. Documented absolute executable selection and private evidence paths in `ops/agent-pipeline/VALIDATION.md`.

- Created the dedicated `fhs-test` minikube cluster on dragonvm (Ubuntu 26.04 Hyper-V guest), Kubernetes `v1.37.1`, containerd `2.3.4`, four CPUs and 4096 MiB RAM. Preserved the existing `monitoring` profile and default context. Added reproducible [bootstrap and live checks](../ops/kubernetes/README.md). The initial BusyBox short-name DNS check exposed a harness exit-status issue; the corrected absolute-name run passed node/system readiness, DNS, Service traffic and PVC write/read across separate pods. The corrected run exited successfully; both smoke namespaces and their PVs are gone. Full-stack deployment remains deferred pending assessment of current development configuration and NetBox values.

- Added persistent lab lifecycle commands and retained bootstrap compatibility. Stop/start took 7.62/48.2 seconds before full-stack deployment; PVC persistence and post-resume smoke checks passed. Host uptime, monitoring containers and default context were preserved.
- The restart test exposed minikube's known PV reclamation issue; all owned marker/probe fixtures were subsequently reclaimed. No global repair is automated. See [evidence and storage limits](../ops/kubernetes/README.md).

- Imported reviewed platform configuration from official development `87dc794`, retaining the existing `monitoring/` snapshot. Added independent pinned Helm releases, VM-only overrides, fresh cluster secrets and a thin [deployment entry point](../ops/platform/README.md). Actual dragonvm checks passed authenticated NetBox CRUD, PostgreSQL pod-recreation persistence, synthetic PDU telemetry through Telegraf/Prometheus/Grafana, and authenticated Elasticsearch/Kibana health. An unchanged monitoring rerun retained service pod UIDs/restart counts.
- Replaced lab storage allocation with static retained hostPath PVs to avoid minikube provisioner restart identity changes. A real NetBox object survived the full cluster stop/start cycle; no profile deletion or database reset was used. Cluster container limit is now 6 GiB. See [validation and limits](../ops/platform/VALIDATION.md).
- Added a separate restricted Bifrost API fixture using a pinned actual image; SQLite initialization, loopback API response and cleanup passed. Nested KVM VM/vCPU creation checks passed. Full guest provisioning and physical hardware behavior remain untested.
- Final optional all-components command `deploy.sh deploy --with-bifrost` passed after full cluster resume, including the corrected transient database-restart cleanup handling. All service pods were Ready; disposable API sites, forwarding processes and Bifrost resources were cleaned up. Default context remained `monitoring`.

- Recorded the user-confirmed VCC/FSP unit composition and full VCC-to-FSP connectivity, with links to the SKA MCS architecture and interface documentation; see [unit topology](unit-topology.md).

- Reconciled provisioning/monitoring documentation with current playbook tags, NetBox export ownership, imported `platform/` configuration and observed VM overrides. Role pages include canonical role READMEs; existing drawings are preserved and two Mermaid flows clarify inventory and monitoring. Fresh Sphinx 7.4.7 `-E -a -b html -W --keep-going` passed on dragonvm using `/home/dragon-lord/fhs-docs-tools/bin/sphinx-build`; the sandboxed attempt failed only on Python inventory DNS. Baseline screening recorded 99 warnings. Loopback Playwright rendered both Mermaid diagrams and captured platform, inventory, users and provisioning pages without page errors; screenshots were inspected privately under `/tmp/fhs-docs-*`. Syntax/list checks used an isolated documentation inventory; no deployment or live inventory polling was run. Independent review is the next controller stage.
- Retired the standalone conversation handoff after reconciling its useful content: workspace/history provenance in [sources](sources.md) and the [environment plan](test-environment-plan.md); controller design/executable/results in existing [workflow](../ops/AGENTS.md), [controller README](../ops/agent-pipeline/README.md) and [validation](../ops/agent-pipeline/VALIDATION.md); VM access/lifecycle in [Kubernetes operations](../ops/kubernetes/README.md); platform and Bifrost facts in their existing operations/validation pages; role findings and proposed test matrix in the environment plan; resource/NetBox ownership in [resource layout](resource-layout.md); telemetry/dashboard proposals in the plan and [backlog](TODO.md). Stale pre-platform and unverified-KVM claims were replaced by dated validation boundaries. Added the user-reported LOCAL wake-script procedure without its MAC; wake behavior and packet receipt remain untested and the script was not executed.

## 2026-10-22

- Corrected two review findings against [the authenticated Elasticsearch readiness probe](../platform/charts/elasticsearch-kibana/templates/elasticsearch.yaml) and [then-active Poetry tasks](https://github.com/DragonLord-64/experimental-fhs-baremetal/blob/a5395d00715ee1a50454fc71e54820901580d7e7/roles/manage_poetry/tasks/main.yml): health checks use the container's protected password; Poetry documentation describes installation only, its existing virtual environment and the site wrapper tag. Strict Sphinx 7.4.7 `-E -a -b html -n -W --keep-going` passed using the external documentation tools after allowing the public Python inventory fetch; sandbox DNS had blocked that fetch. Poetry wrapper syntax/task selection and health-command shell syntax passed without contacting targets. Loopback Playwright checks rendered both Mermaid diagrams and representative built pages without page errors; private captures remain under `/tmp/fhs-docs-*`. No runtime service, provisioning or wake-script checks were performed. Independent review remains the controller's next stage.

- Established the actual `manage_users` container test on dragonvm: fresh state, unchanged rerun, sudo policy change, observed container drift and repair all passed; owned container cleanup passed. See [commands, evidence and limits](../ops/role-tests/manage_users/molecule/default/VALIDATION.md). Bifrost guest provisioning and physical hardware remain unverified.

- Added a bounded synthetic logging fixture for canonical `vccunit1-fhs1`, an explicit file-input Filebeat overlay preserving the role priority mapping, and a supervisor-only ingest/restart verifier. Offline checks pass; live journal feasibility, ingest, permissions and Discover evidence remain pending. See [commands and limitations](../ops/platform/logging/README.md) and [validation](../ops/platform/logging/validation.md). No existing journal role or telemetry producer changed.

- Supervisor executed scoped logging bootstrap and two finite real Filebeat 9.5.5 runs against the existing lab Elasticsearch 9.5.5: six exact events each for `vccunit1-fhs1`, retained fields/timestamps, clean registry restart and invalid credential rejection passed. Used the explicit filestream fallback because no supported journal importer is installed; no journald/Ansible coverage claimed. Discover proof and final inspection remain pending. See [actual evidence](../ops/platform/logging/validation.md).

- Supervisor completed the owned Kibana data view and real Discover capture; implementation visually inspected six filtered rows for `vccunit1-fhs1`, levels, IDs, service and timestamps without credentials. Supervisor verified owned cleanup; the completion gate passed after the asynchronous response. [Validation](../ops/platform/logging/validation.md) retains the filestream/journald distinction, clean-restart limit and missing post-run memory/Kibana API version measurements. Fresh independent review remains controller-owned; Grafana scope is unchanged.

- Promoted active [NetBox helpers](../playbooks/netbox) and [switch POAP](../playbooks/switch-poap) into first-class playbook directories, moving all tasks, plugins, module utilities, requirements and scripts together. Updated paths and documentation; production role bodies and all other playbooks remain unchanged. Static path/source checks passed; no hardware, DHCP or NetBox operations were run.

- Archived the user-approved CIS audit/prototype, node, BIST, gRPC, exporter/Prometheus, EXDS and development Filebeat entry points under [playbooks/archive](../playbooks/archive/README.md). Bodies remain unchanged except the CIS audit artifact paths, adjusted to resolve to the same existing files after relocation. Kept current top-level entry points, card test and other development playbooks in place; no playbook was executed.

- Consolidated cluster definitions in top-level `platform/` and removed the duplicate `monitoring/` tree. All 16 non-README files were byte-identical to their platform counterparts, including metric captures; the platform README already preserves and corrects the former instructions. Updated current provenance notes; no deployment, Helm apply or service restart was run.

- Added the synthetic [mesh capacity](../examples/grafana-static-demo/screenshots/mesh-capacity.png) and [switch ports](../examples/grafana-static-demo/screenshots/switch-ports.png) screenshots to the [static demo README](../examples/grafana-static-demo/README.md) for GitHub viewing. Image hashes, PNG dimensions and relative links passed static checks; no runtime services were changed.

- Completed the [static demo screenshot gallery](../examples/grafana-static-demo/README.md#screenshots) with rack, FHS, interface and VLAN captures alongside mesh capacity and switch ports. All six PNGs passed integrity, hash and relative-link checks; no runtime services or dashboard configuration changed.

## 2026-10-23

- User authorized lab NetBox rebuilds, test-data removal and resource changes without further confirmation; recorded in [AGENTS.md](../AGENTS.md#lab-test-authority). Host shutdown/reboot remains prohibited.
- Tested MIT-licensed NetBox Inventory `2.7.1` on isolated NetBox `4.7.0`: 17 real API checks and fresh independent review passed. Synthetic DAC serial, faulty status and quarantine shelf remain searchable; an FPGA asset survives installed-module deletion with its serial and change history. Actual UI screenshots are retained in the ignored `ops/agent-pipeline/runs/netbox-inventory-trial-20261023/` evidence bundle. [Reproduction and limits](../ops/platform/inventory-trial/README.md): DAC lifecycle is manual, faulty status does not enforce reuse prevention, and default change-log retention is 90 days.
- Corrected existing lab NetBox web resources to two workers and a 2 GiB limit after a concurrent management command caused OOM. [Concurrent API/management validation](https://github.com/DragonLord-64/experimental-fhs-baremetal/blob/466522bf2dff260ab8f76c1a9c999331233125b1/ops/platform/netbox-resource-test.py) passed 62 API requests without OOM or pod restarts; 186 devices remained and logging stayed stopped. See [platform operations](../ops/platform/README.md).
- Fixed the portable static Grafana demo in commit `62422f12ddb69551bc1a13ded1488dc1a40d3d15`. Rack switch summaries now include member faults; mesh available capacity shows zero on failed links and varied deterministic percentages on healthy links. Configured line rate and physical hardware states remain separate. Nineteen unit/HTTP checks, fresh independent review and 14 real Compose/Grafana/browser/portability gates passed on dragonvm. The final ZIP with refreshed screenshots also passed extraction/launch/query checks; ZIP and evidence are under `/tmp/fhs-grafana-static-fix-evidence/`. Existing NetBox and Kubernetes workloads were not changed by this demo run.
- Added a portable [single-release platform chart](../platform/charts/fhs-platform/README.md) with bundled dependencies, configurable namespace/URL prefix, fresh PostgreSQL/Valkey, optional copied external database and six provisioned runtime dashboards. [Eight real render/mock-API checks](../ops/platform/umbrella/README.md) passed, including upgrade credential preservation and actual dashboard unpacking. Manifests contain no cluster-scoped configuration resources or external Services; existing storage/ingress and capacity still require local checks. No hardware cluster was accessed or deployment performed; independent review is next.
- Fresh independent review of the [portable chart](../platform/charts/fhs-platform/README.md) found no actionable issues. Seven checks passed independently; its sandbox blocked only the loopback mock, which passed in the full eight-case implementation run with permission. The cached pinned Grafana image also verified init/probe tools and prefix substitution in a temporary UID-472 container with no network or host mounts and a read-only root. The standalone packaged chart rendered and passed manifest acceptance. Hardware login, routing/TLS, storage binding, migrations, telemetry and shared capacity remain unverified.
- Corrected the [portable chart's NetBox launcher](../platform/charts/fhs-platform/values.yaml) to serve static assets under the shared URL prefix, retaining initialization and its other Granian settings. Earlier manifest checks missed the pinned image's hardcoded `/static` route. The [new launcher regression](../ops/platform/umbrella/README.md) failed before the fix and passed for five prefixes afterward; all nine umbrella tests, six logging tests and both chart lints passed. The actual pinned image served four JS/CSS assets with HTTP 200 for all five prefixes in an isolated UID-1000 container on `dragonvm`, bypassing database initialization for that check. No hardware deployment, migrations, ingress/TLS or browser verification was performed; independent review is next.
- Fresh independent review of the NetBox static-route fix found no actionable issues. It verified the pinned entrypoint always initializes before executing the launcher, all five prefix cases and existing logging/lint checks; its sandbox blocked only the loopback mock already passed in the implementation run. A normalized before/after Helm render changed only `Deployment/fhs-netbox`. The fix is published to the private experimental `development` branch; hardware ingress and browser confirmation remain pending.
- Added the [upstream-documented media affinity](../platform/charts/fhs-platform/README.md) to the regular chart values: NetBox web, worker and housekeeping share a node by chart/release/component labels in the same namespace, retaining the original `ReadWriteOnce` PVC and no fixed node. The [render regression](../ops/platform/umbrella/README.md) failed before implementation; all ten umbrella tests passed with loopback permission and both chart lints passed afterward. Documented removal of the existing temporary web node selector after upgrading. No cluster deployment, multi-node scheduler or CSI attachment test was performed; independent review is next.
- Fresh independent review of the NetBox media affinity found no actionable issues. It verified the pinned chart's documented pattern, rendered label scope and self-matching startup, disabled-worker case, and post-upgrade removal of only the temporary hostname selector. The focused regression passed independently; full-suite and lint evidence are recorded above. Hardware multi-node scheduling and CSI recovery remain unverified.
- Recorded the user's [current native NetBox testing priority and deferred spare-parts scope](decisions.md#confirmed-with-the-user--2026-10-23). Clarified the existing [lab integration target](../AGENTS.md#lab-test-authority): chart/importer integration belongs on dragonvm's `fhs-test`; standalone plugin tests and renders did not close that gap. The trial's cleanup boundary did not prohibit authorized lab integration testing. This documentation change establishes no new runtime test result.
- Re-ran the current [read-only NetBox resource/API check](https://github.com/DragonLord-64/experimental-fhs-baremetal/blob/466522bf2dff260ab8f76c1a9c999331233125b1/ops/platform/netbox-resource-test.py) over SSH against the existing `fhs-test` / `fhs-platform` deployment: 62 API requests passed alongside a Django read; 186 device records, pod UID and zero restart count remained unchanged, with no OOM events and no server plugins enabled. The remote checkout lacked this newer script, so the checked local source was supplied through SSH stdin. This verifies existing native NetBox health, not the delivered umbrella chart or an importer end-to-end run.

- Ingested the published development history through `f0603c6` into the wiki, preserving the existing append-only log and local handoff edits. Added [latest changes](latest-changes.md) for the portable six-dashboard static demo, capacity/port semantics, screenshots, native dashboard source and current NetBox playbook paths. Verified source files in a separate read-only history inspection; runtime results are attributed to their existing evidence, not rerun here. The working checkout remains at `455023d`; no deployment or inventory changes were made.

- Recorded the user's revised [NetBox import/replacement decision](resource-layout.md#import-decision--2026-10-22): intentional reimport overwrites observed facts; serial identifies hardware, IP provides access; confirmed replaced modules are deleted and recreated; cabling must be freshly verified. The user selected NetBox journals for history, attached to the surviving parent rather than the deleted module. This supersedes retaining uninstalled module records; implementation and live acceptance remain pending. Reviewed the wiki refresh and passed `git diff --check`; existing local handoff edits remain preserved.

- User accepted scoped absence reconciliation and selected standard YAML Ansible inventory as the common discovery/import/export interface. Recorded the [contract direction](resource-layout.md#import-decision--2026-10-22): separate real discovery from testable controller-side NetBox reconciliation; structured hardware host variables carry explicit scope/completion. No importer/exporter changes or live mutations were performed.


## 2026-10-24

- Safely fast-forwarded the primary checkout to published `eee2d6d`, preserving unrelated notes and the untracked emulator candidate in private backups and on disk. Reviewed official `development2` at `0658e93`; the chart/moves were already represented. Added missing placeholder-MAC guards and the existing deployment profile; [older source gaps](../ops/platform/inventory-alignment/UPSTREAM.md) remain separate.
- Aligned the main lab and portable chart with shared NetBox `4.7.0` / MIT Inventory `2.7.1` image/configuration. Actual main upgrade preserved 186 devices; 62 concurrent read-only API checks passed without OOM or pod restarts. A fresh scoped delivered-chart NetBox deployment on existing `fhs-test` passed migrations, readiness, runtime plugin/sync and prefixed login/static checks. Logging remained stopped. The custom image is built/loaded in the lab, not published to a registry.
- Unified Linux/Nexus import through one public entrypoint and added serial-identified assets, retained replacement/removal history and scoped absence handling. Initial independent review found partial FPGA, rename ownership and retry gaps; a fresh worker fixed them. Final validation: 38 alignment checks, ten umbrella checks, both importer syntax checks and 69 real native Ansible/API checks, including actual comparison tasks and cabled refusal. [Evidence and boundaries](../ops/platform/inventory-alignment/VALIDATION.md): no physical discovery, full-stack activation or ingress/TLS acceptance claimed. Motherboard FRU serial is never substituted for unavailable chassis identity.

- Applied the user's single-pass implementation policy and standing automatic private-push order. The controller launches one implementation worker, keeps configured checks mandatory and records user review pending; legacy review checkpoints resume implementation. Twelve controller tests passed, including no review launch, preserved interruption/cancellation, failed-check blocking and legacy resume. Existing paused runs were not resumed.

- Separated portable source from private lab material: dashboard development/captures and the custom role harness now live under `ops/`, the lab plan under `wiki/`, and the shared guide describes portable deployment. Official docs/tests retain their paths; original Molecule entrypoints remain separate from the relocated tested scenario. [Copy/sync map](source-boundary.md) and [provenance/checks](../ops/source-boundary/README.md) record six boundary checks, 47 dashboard, 19 demo, 38 importer, ten chart and 12 controller checks, plus a strict Sphinx build. No deployment or new live role run was performed.

- Added optional local IPMI FRU discovery with separate chassis, product and motherboard identities, per-field provenance and safe DMI/override precedence. Missing data leaves new optional values empty and preserves existing records; motherboard absence never authorizes removal. [Validation](../ops/platform/inventory-alignment/VALIDATION.md#optional-fru-identity--2026-10-24): 50 local checks, 16 native FRU checks and 69 asset/history checks against the isolated delivered-chart NetBox on `fhs-test`; both importer syntax checks passed. Private photo/serials were replaced by synthetic fixtures. No production hardware access was performed.

- Simplified portable Inventory installation after a hardware `ImagePullBackOff` report: the chart now uses the public NetBox image and installs pinned, hash-verified Inventory automatically as UID 1000 in per-pod volumes. Actual scoped lab upgrade and web-pod replacement passed; nine devices/48 assets retained, plugin/worker/management/API/login/static checks passed. Main 186-device instance remained unchanged. Twenty-three focused checks and chart lint passed; [evidence and PyPI startup requirement](../ops/platform/inventory-alignment/VALIDATION.md#automatic-plugin-installation--2026-10-24). Hardware Events were not supplied and no hardware deployment was performed.

- Aligned the [platform install/upgrade README](../platform/charts/fhs-platform/README.md) with official SKA `development2` at `7b0a306` (`mid-cbf-hw`, `hw-management`, `/mid-cbf-hw`). Retained the experimental public-image/automatic Inventory installation path and portable validation guidance; no workloads or values changed. Six source-boundary checks and `git diff --check` passed.

- Shortened the [platform README](../platform/charts/fhs-platform/README.md) to high-level installation, update, verification and access commands at the user's request. Six source-boundary checks and whitespace validation passed; no runtime configuration changed.

- Restored the [platform chart README](../platform/charts/fhs-platform/README.md) byte-for-byte from official SKA `development2` `7b0a306`, as requested, superseding the earlier adaptations and shortening. Verified source byte equality and whitespace; no deployment configuration changed.

- Made `platform/README.md` a short pointer to the canonical chart README, removing the competing legacy deployment guide. The user-confirmed SKA `development2` README remains byte-identical to `7b0a306`; its exact hash and original validation link are recorded in source-boundary provenance. Six boundary checks passed. All edits remain experimental-only; upstream push stays disabled.

- Added opt-in NetBox custom-field Prometheus discovery, a public HW home and setup-only Filebeat initialization in the experimental chart. [Full-stack validation](../ops/platform/discovery-portal-setup/VALIDATION.md) passed on existing `fhs-test`: 69 inventory/history plus 16 FRU checks before and after upgrade, real exporter lifecycle refresh, prefixed routes/browser login pages, limited log writes and reapply preservation. Credentials, PVCs and six unrelated workloads were preserved. The canonical README remains byte-identical to official `development2`; no official repository or physical hardware was changed.

- Added hash-pinned Topology Views `5.0.0` to the existing NetBox public-image startup and optional image recipe. [Focused check](../ops/platform/topology-views/README.md) covers all consumers, writable static files and a controller-only retained-release smoke with a rolled-back synthetic cable fixture. Three focused tests, six discovery chart contracts and Helm lint passed; live plugin validation remains pending controller execution. No deployment or image build was performed.

- Completed [Topology Views focused lab acceptance](../ops/platform/topology-views/README.md): authenticated topology and synthetic cable connection, CSS/JS, migrations, credentials/PVCs and scale restoration passed in 78.42s. Corrected the probe route and Helm-history comparison; the plugin installation itself needed no runtime fix. Three plugin tests, six existing chart contracts and Helm lint passed. No physical discovery or browser visual validation claimed.

- 2026-10-24: Extended the existing installation home with operator Markdown,
  named links and cached website reachability through the shared ingress.
  Six focused runtime/chart tests, 13 discovery/home, ten umbrella and three
  Topology Views checks plus Helm lint passed
  locally. Added the controller-only full-chart landing acceptance entrypoint;
  live root/subpath and failure/recovery results remain pending.
  [Settings, checks and limits](../ops/platform/landing-page/README.md).

- Completed [installation-home acceptance](../ops/platform/landing-page/README.md) in the delivered chart: deployment-derived links, operator Markdown/custom links, cached 60-second website status and controlled failure/recovery passed through the shared ingress at root and prefixed paths (301.51s). Credentials/PVCs and original lab scales/settings were preserved. Browser rendering was inspected. Retained the authorized lab memory fix (8GiB / 10GiB with swap); no host or cluster restart. Removed context flags from the changed check READMEs; validated lab targets stay inside the scripts.

## 2026-10-24 — pipeline cleanup and scope limits

- Inspected FoodReserve-2D’s current GitHub task lifecycle and manager guidelines; adapted local intake/scout, one worker, FIFO dispatch and a bounded cluster/setup helper. Omitted its advisory review and editor-specific machinery. [Commands and sources](../ops/agent-pipeline/README.md).
- Set small-task defaults to 600 seconds per worker, 120 per configured check and three launches. The controller owns acceptance; workers avoid duplicate checks and unrelated test infrastructure. Added the same fast source-check entrypoint to private GitHub CI, with controller tests only for Python controller changes. Scope paths are guidance, not sandbox enforcement.
- Syntax audit found and fixed empty disabled shell groups in the hardware power-test launcher; no hardware test was executed. Corrected Bifrost Quickstart and lab Inventory-image links. Existing wiki/emulator work was preserved. Final validation and limits: [pipeline validation](../ops/agent-pipeline/VALIDATION.md#2026-10-24--intake-scout-and-manager).

## 2026-10-25 — temporary Filebeat setup disable

- Disabled the [platform Filebeat setup default](../platform/charts/fhs-platform/values.yaml) while the image pull is unavailable; setup remains opt-in and the writer account remains enabled. Focused contracts: 13 passed; Helm lint passed. Logging resources passed server dry run on `fhs-test` with existing lab storage overrides. Full chart/importer runtime acceptance was not run; no live release was upgraded.

## 2026-10-25 — delegated Filebeat index setup

- Added [control-host index setup](../roles/filebeat/README.md#elasticsearch-setup)
  using the exact device Debian package and a separate setup API key or login.
  Setup preloads the default template/data stream and ILM policy before device
  services start; temporary credentials are removed on success or failure.
- Role playbook syntax and the delegated synthetic-package fixture passed (API
  key, password, failure cleanup and check mode). Live Elasticsearch and device
  journal ingestion were not exercised; ansible-lint was unavailable.

## 2026-10-25 — LLDP and FPGA DAC import

- Extended the [unified NetBox importer](../playbooks/netbox/README.md#topology)
  with LLDP and exact DAC serial reconciliation, preserving occupied/ambiguous
  endpoints. Native cables appeared in Topology Views with Inventory active.
  [Evidence and limits](topology-import.md): 64 importer tests, two syntax checks,
  native topology acceptance and 69 existing asset checks passed in the lab.

## 2026-10-25 — wiki consolidation

- Consolidated the retired handoff and historical dashboard snapshot into the
  [topic index](INDEX.md), [source map](sources.md), [environment evidence](test-environment-plan.md)
  and [dashboard/telemetry note](latest-changes.md). Preserved the original
  handoff and pre-lint wiki copies under the ignored private
  `ops/agent-pipeline/runs/wiki-lint-20261025/` directory. Earlier log entries
  and local user notes remain intact.
- Reconciled [inventory policy](resource-layout.md) with recorded asset, FRU and
  topology acceptance; kept normalized discovery YAML marked as design work.
  Updated stale checkout paths, pipeline stages, lab memory history, image-recipe
  location and documentation backlog. All claims come from repository sources
  and dated results; no lab or physical-hardware check was rerun.
- Wiki-only source/link checks and a local structure/fragment inspection pass:
  one title per page, balanced fences, valid local paths/fragments and no trailing
  whitespace. No external-link reachability or Sphinx build was claimed.

## 2026-10-25 — shared NetBox playbook defaults

- Centralized [import/export defaults](../playbooks/netbox/defaults.yml), including
  the single `netbox_credentials_file` setting. CLI overrides remain supported;
  runtime device facts and routing stay in the playbooks. Six routing checks,
  seven synthetic task checks and both playbook syntax checks passed. No live
  inventory or chart changes were needed for this configuration refactor.

## 2026-10-25 — queued discovery completion

- Queued `netbox-discovery-completion-20261025` with the user-approved
  [QSFP/topology/placement scope](../ops/platform/inventory-alignment/tasks/discovery-completion.md)
  and [issue #16](https://github.com/DragonLord-64/experimental-fhs-baremetal/issues/16).
  Seven original user screenshots are retained unchanged in ignored private
  pipeline evidence with SHA-256 provenance. Sanitized representative fixtures
  and full chart/importer/plugin acceptance are required; implementation has not
  started. Task source/link checks passed.

## 2026-10-25 — pipeline proposals

- Recorded [shared hardware reservations and stuck-work maintenance](TODO.md#pipeline-proposals--not-approved-for-implementation)
  as future ideas only. Neither is implemented or approved for implementation;
  pipeline behavior is unchanged. Documentation source/link checks passed.

## 2026-10-25 — discovery implementation prepared for controller checks

- Prepared dynamic QSFP/module metadata, verified FPGA DAC grouping, LLDP identity
  resolution and optional rack-unit/independent power-inlet reconciliation.
  [Operator schema](../playbooks/netbox/README.md#optional-server-placement-and-power).
- Read official `development2` `4533a85` and all seven private images; all original
  image SHA-256 hashes match the preserved index. Published only
  [sanitized representative fixtures](../ops/platform/inventory-alignment/fixtures/discovery/README.md).
- Added the [controller acceptance entrypoint](../ops/platform/inventory-alignment/acceptance_discovery.py).
  [Acceptance remains pending](../ops/platform/inventory-alignment/VALIDATION.md#discovery-completion--controller-pending);
  no worker deployment, controller checks, publication or hardware success.

## 2026-10-25 — focused task creation and acceptance

- Recorded the user's feedback in [task creation guidance](task-creation.md):
  bound acceptance to changed behavior, reuse existing checks and avoid making
  a practical implementation into a harness project. Linked it from task intake
  and worker rules. Four documentation/source-link checks passed.
- Redirected the existing NetBox discovery task to finish its implementation
  with focused tests, preserving its feature scope and partial work. Controller
  acknowledgement was observed; native acceptance remains pending.

## 2026-10-25 — discovery focused controller handoff

- Narrowed the existing [native discovery harness](../ops/platform/inventory-alignment/discovery_native.py)
  to the supervisor's requested checks, retaining seven LLDP links, QSFP/DAC,
  existing cables, idempotence, placement/power and authenticated plugin evidence.
  Successful empty LLDP reads now explicitly report connection preservation.
- Re-fetched official `development2`: still `4533a85`. Controller acceptance
  remains pending; no worker deployment, publication or physical hardware claim.
- Evidence/documentation checks: seven original SHA-256 hashes match; 19 local
  documentation link targets exist. These checks cover provenance/docs only;
  runtime acceptance is reserved for the controller.

## 2026-10-25 — focused discovery acceptance completed

- Completed the queued discovery changes after the user's focused-test redirect.
  Corrected fixture variable precedence and Ansible-tagged rack-unit validation
  exposed by native acceptance. [Observed results](../ops/platform/inventory-alignment/VALIDATION.md#discovery-completion--accepted-2026-10-25):
  focused fixtures/syntax and 50 native report assertions passed on the retained
  chart, including seven LLDP links, two DACs, Inventory metadata, Topology Views,
  rack placement and both PDU cables. Hardware reads remain unverified.


## 2026-10-25 — hardware type corrections and host isolation

- Hardware manufacturer/model observations now correct NetBox device and linked
  chassis asset types while retaining asset IDs/tags/history. Bootstrap identity
  values are fallbacks; type resolution uses manufacturer/model and numeric IDs.
- Import failures stop the affected host while other hosts/families continue;
  failed imports do not contribute shared topology observations. Missing optional
  observations preserve known data; ambiguous serial ownership still needs review.
- [Validation](../ops/platform/inventory-alignment/VALIDATION.md#hardware-corrections-and-host-isolation--2026-10-25):
  49 focused tests, real Ansible syntax, 20 native FRU and 69 importer assertions
  passed against the retained chart on `fhs-test`. Physical hardware unverified.


## 2026-10-25 — one FRU device identity source

- User-directed policy: explicit identity overrides precede the selected IPMI
  FRU. Linux DMI/sysfs no longer supplies device/product/motherboard identity.
  Device serial prefers FRU Chassis Serial, then Product Serial; never Board Serial.
  This supersedes the prior bootstrap-fallback precedence.
- A valid serial creates a device even without manufacturer/model (`NA` /
  `Unknown`). Missing observations preserve known values; DIMM/NVMe discovery
  retains its existing sources. Compare, placement and apply share normalized
  identity without separate bootstrap fallbacks.
- [Validation](../ops/platform/inventory-alignment/VALIDATION.md#fru-identity-and-serial-only-creation--2026-10-25):
  50 focused tests, real Ansible syntax, 21 native FRU and 69 native importer
  assertions passed on the retained chart. Physical hardware remains unverified.


## 2026-10-25 — incremental import stages

- Added `servers`, `modules`, `interfaces`, `ips`, `cables`; default/`apply` runs
  all. Later stages skip missing parents. Chassis writes precede optional probes;
  component writes follow discovery. Roles default to Unassigned; category tags
  keep grouping independent of role and actual FRU part/model.
- Removed absence-removal paths and staging-type preflight. Observed component
  updates preserve installed IDs/cables and retain old assets as stored history.
  FRU PSUs and serial-bearing QSFPs are inventory items; module-only runs do not
  explicitly create interfaces. Captured NIC EEPROM metadata is retained.
- [Validation](../ops/platform/inventory-alignment/VALIDATION.md#incremental-tagged-import--2026-10-25):
  fast static data checks, eight live scenario checks, authenticated
  Inventory asset and Topology Views graph. Physical hardware remains unverified.
- Automatic approval blocked destructive cable-conflict replacement and removal
  of IP/MAC ownership safeguards; existing network conflicts remain reported.

### 2026-10-25 — Standalone hardware reference capture

Added [raw reference capture](../playbooks/netbox/capture_reference.yml) for
`sys1391` and `nx00EF0`: raw command results, Linux facts and per-interface/card
probes, without NetBox writes. Static collector fixtures checked missing tools,
timeouts, NVMe namespaces and SDK/ethtool enumeration. Ansible syntax checked
on dragonvm. Physical collection is for the user to run and return as evidence.

### 2026-10-25 — Reference capture SDK environment correction

The [capture playbook](../playbooks/netbox/capture_reference.yml) now resolves
SDK settings from target inventory with importer precedence. It sets venv PATH,
BWSDK_ROOT and locale after switching to the tooling user; unresolved users are
reported rather than silently probing as root. Static card/QSFP invocation
checks and Ansible syntax validation on dragonvm passed; hardware not contacted.

### 2026-10-25 — Reference command and connection coverage review

Reviewed the standalone capture against importer probes and tool/Cisco command
references. Added exact memory/BIOS/nproc probes, port-specific PCI/VPD, decoded
and hex optical EEPROM, detailed LLDP, USB tree and explicit FPGA PCI mappings.
Capture honors target server-info path, BMC channel and command PATH. User scoped
connections to LLDP; PDU ports, VLANs and additional network discovery are out
of scope. Static fixtures passed; Ansible syntax checked before the final scope
trim. Physical hardware was not contacted.

### 2026-10-25 — Product serial identifies the server

Reviewed corrected upstream reference at `a41dc8f`. Changed FRU identity to use
Product Serial (SYS number) only, apart from existing explicit serial overrides.
Chassis Serial is retained as `chassis_serial`; Product Name is retained as the
reported `manufacture_date` and no longer participates in model selection.
Product Part Number supplies the model; Board fields identify the motherboard.
Server-info remains optional supplemental placement/role/PDU metadata.
Corrected sys1392 now includes LLDP and FPGA/QSFP output. Five FPGA connector
serials have opposite-suffix switch counterparts; no automatic suffix matching
was added in this change. No tests or hardware commands run, per user instruction.

### 2026-10-25 — Import failures from hardware run

Screenshots showed OOB assignment during interfaces stage before BMC address
creation in ips stage. Moved assignment after address creation in ips and used
an explicit address lookup. Serialized early server/switch creation to avoid
parallel hosts racing to create shared site/role/type prerequisites. The switch
HTTP 500 is consistent with a shared-role creation race (one switch succeeded),
but the screenshot alone cannot establish the server exception. No tests or
hardware commands run, per user instruction.

### 2026-10-26 — FPGA DAC paired-end matching

Added the FS QDD-400G-PC01 BASE-1/BASE-2 convention observed in corrected sys1392
and nx0EF00 references. Exact serials and explicit endpoint mappings retain
precedence. Automatic matching requires matching vendor/part and one physical
FPGA connector plus one switch connector; reused/ambiguous bases remain omitted.
Both complete endpoint serials and existing occupied-cable protections remain.
No tests or hardware commands run, per user instruction.

### 2026-10-25 — User accepted the working hardware import

The user reported “the import worked” after `b966fb7` and asked to lock in the
result. Recorded the [working baseline](netbox-import-baseline.md), source tag,
identity/connection rules, failure boundaries and deferred improvements. This is
user-reported hardware success, not a claim of independently observed complete
coverage. Future changes should be small and explicitly scoped. Documentation
only; no importer, hardware or lab changes in this milestone.

### 2026-10-26 — Inventory unresolved observed DACs

Added native DAC cables with a dedicated unknown endpoint per cable on a tagged
per-site placeholder device. Full observed connector identities and properties
remain on the cable. A later unique opposite-end observation can replace only
the importer-managed placeholder, retaining the same cable ID across runs.
Real occupied endpoints, optical-only observations and absent hardware retain
the working baseline's protections. No tests, hardware or lab commands run,
per user instruction; user hardware validation remains pending. See the
[importer README](../playbooks/netbox/README.md).


### 2026-10-26 — Serialize component writes and omit logical interfaces

Added per-task serialization to observed inventory/QSFP, switch-module and
pluggable-association writes; NIC/FPGA and chassis writes were already serialized.
This addresses the likely shared-type creation race behind the reported HTTP 500;
the server traceback was not available to prove its cause. Linux interface,
address and LLDP discovery now uses hardware-backed interfaces, retaining USB,
explicit BMC and FPGA ports. Existing logical records are preserved. No tests,
hardware or lab commands run, per user instruction; hardware validation pending.

### 2026-10-26 — Platform APT cache

Added an enabled-by-default apt-cacher-ng Deployment, Service and retained 20Gi
cache claim to the [platform chart](../platform/charts/fhs-platform/README.md).
The user's five configuration overrides replace the pinned image's broad CONNECT
settings; other daemon settings remain packaged defaults. Service exposure and
storage are configurable; [client settings](../platform/charts/fhs-platform/CONFIGURATION.md#apt-cache).

Helm lint and enabled/disabled renders passed (existing Grafana probe warnings).
On dragonvm, chart-rendered resources were applied alongside the retained
`mid-cbf-hw` release in `fhs-discovery-portal-test`, context `fhs-test`, with
`standard` storage. Service HTTP downloads matched across two requests; the
cache log showed 140038 inbound bytes initially and 761 on revalidation for
138891 outbound bytes each time. CONNECT to deb.debian.org:443 returned 200;
example.com:443 returned 403. Cached Release data survived pod replacement.
The umbrella applications were scaled down before testing and left unchanged;
no full-stack upgrade or native importer rerun is claimed. Importers unchanged.
Lab resources remain available for inspection; logs are ephemeral. Only one
allowed CONNECT host was exercised; the exact allowlist is in the ConfigMap.

### 2026-10-26 — Portable NetBox JSON transfer

Added the [inventory CLI](../playbooks/netbox/README.md#portable-inventory-json)
with schema-filtered export, portable relationships, create/update import,
read-only preview, protected files and explicit partial reports. Inventory plugin
objects remain unsupported. Three focused local behavior tests and whole-file/
inline Vault checks passed. A disposable native fixture on existing `fhs-test`
passed nine assertions over 20 objects, including destination IDs, management IP,
dual PSU/network cables, nested JSON and unchanged rerun. Actual CLI export
returned partial status with reported omissions; no all-field migration claim.
See [exact results and limits](../ops/platform/inventory-alignment/TRANSFER-VALIDATION.md).
Controller owns source checks and publication; neither was run by this worker.

- 2026-10-26: Nexus management import now observes an explicit interface/address
  prefix, reconciles interface ownership and primary IPv4/IPv6, and preserves
  addressing on missing/ambiguous/conflicting evidence. Focused contracts and
  native retained-chart preview/apply/repeat passed; physical NX-OS remains
  unverified. See [validation](../ops/platform/inventory-alignment/NEXUS-MANAGEMENT-VALIDATION.md).

### 2026-10-26 — Role cleanup, stages 1–2 (overall task incomplete)

Fetched official development2 at `7704587034e7e41f1b1266c109b0e903279617a9`.
Unified BittWare identity, preserved supplementary groups, repaired venv ownership/
permissions, replaced runner's Python-specific sentinel and made development sudo
an explicit named-account inventory opt-in. One isolated Molecule fixture passed
unchanged rerun, permission checks and observed drift repair with an inert SDK.
DPDK now records success only after a full installation, skips unchanged inputs
and rebuilds changed/failed inputs; a small real C build checked these paths.
Fixed GRUB's hardcoded hugepage count, removed automatic reboot execution and
made firmware require its explicit tag. No hardware, firmware, GRUB application
or deployment was tested. HTML docs built with recorded warnings. Stages 3–6
remain unfinished; no whole-task readiness or production claim. See
[commands, results and resume boundary](../ops/role-tests/cleanup/EVIDENCE.md).

### 2026-10-26 — Role cleanup, stage 3 (overall task incomplete)

Node preparation now requires reviewed versions, renders registration labels/
taints without joining, keeps Ceph optional and avoids containerd rewrite/restart
on unchanged content. Network configuration preserves unrelated files, checks
inputs before writes, disables only cloud-init networking and owns resolved/
timesyncd. CIS policy targets explicit Linux membership beyond Kubernetes nodes;
enforcement remains intentional, with reboot/firewall/time-service and audit
halt-action guards. Deferred patch/password-quality/AIDE policy awaits user review.
Targeted syntax, offline file/template checks and effective-policy fixtures passed;
HTML built with recorded existing warnings. No isolated VM was available, so no
network/kernel/CIS application or hardware validation is claimed. Stages 4–6 and
supervisor runtime acceptance remain. See [evidence and transfer prerequisites](../ops/role-tests/cleanup/EVIDENCE.md).

### 2026-10-26 — Role cleanup stage 4 source and stand-in checks

- gRPC now owns pinned Poetry setup, selects one NetBox controller tag, preserves
  release locks/dependency differences and uses unprivileged, change-driven units.
  Retired standalone Poetry role/callers; corrected actual CLI and FSP paths.
- BIST remains installation/configuration only: supplied pinned requirements,
  no automatic hardware-test service start or trace-file requirement.
- Syntax, real Poetry stand-in installation, unchanged rerun, permissions,
  controller switch, approved source/lock override and Sphinx HTML passed with
  recorded warnings. Real systemd/controller dependencies/SDK/hardware remain
  limits; stages 5–6 and supervisor runtime acceptance remain outstanding.
- [Focused evidence](../ops/role-tests/cleanup/EVIDENCE.md),
  [selected-release packaging](../ops/role-tests/cleanup/PACKAGING.md).

### 2026-10-26 — Role cleanup stage 5 monitoring source and package checks

- Exporter installation now skips unchanged archives, checks console imports,
  rejects writable privileged code and uses a dedicated root-owned venv. Added
  observed missing startup dependencies; local Prometheus integration is optional.
- Monitoring archive changes notify the matching service; configuration uses
  real promtool validation, private auth hashes and root-owned configuration.
  Corrected downloader URLs/checksums to the existing role release pins.
- Preserved Filebeat's controller-only setup, separate credentials and package
  extraction; real device package/config/process checks and existing setup fixture
  passed. Binary version changes, same-path binary repair, unchanged reruns and
  exporter permission/incomplete-install checks passed in a bounded container.
- Sphinx HTML built with recorded existing warnings. Real systemd, live
  Elasticsearch, vendor SDK/MFT and hardware remain limits. Stage 6 and supervisor
  real fhs-test chart/runtime acceptance remain outstanding.
- [Focused commands, results and transfer prerequisites](../ops/role-tests/cleanup/EVIDENCE.md).

## 2026-10-26 — role cleanup source stage 6

Added pinned prebuilt devpi (persistent `/var/devpi`, 3141) and restricted Squid
Git proxy (3128) to the platform chart; preserved existing APT cache. Consolidated
role selection at site callers, retained explicit firmware gates, restored rsync
package/service tasks at the end of site and documented transfer prerequisites.
Helm render/lint, focused offline syntax/tag gates, real disposable pip/Git/APT
fetches and Sphinx HTML passed; five known docs warnings remain. Devpi startup
needed 1Gi after an observed 512Mi OOM. No deployment or hardware/systemd claim.
All six source stages ready for review; supervisor real `fhs-test` chart/Service/
PVC acceptance remains. [Evidence and transfer commands](../ops/role-tests/cleanup/STAGE6-HANDOFF.md).


## 2026-10-26 — Role cleanup and proxy acceptance

Completed six bounded cleanup stages against official development2 `7704587`,
preserving consolidated docs and the Filebeat controller setup. Focused role
installation/rerun/permission/build/selection checks and Sphinx HTML passed with
recorded limits/warnings. The existing delivered-chart lab now includes APT,
persistent devpi and restricted Squid; actual Service package/Git fetches and
devpi cache persistence passed. Source and transfer summary:
[cleanup handoff](../ops/role-tests/cleanup/STAGE6-HANDOFF.md); observed checks and
remaining hardware/system limitations: [evidence](../ops/role-tests/cleanup/EVIDENCE.md).
No official repository changes or production deployment.

## 2026-10-26 — Late development2 transfer preparation

Fetched official `58d49fe` and reconciled the late LLDP placement and DNS-resolver
restart with the accepted cleanup, retaining change-triggered handlers and strict
APT error reporting. Latest official broadens node targeting and disables BIST;
those behavior choices remain explicitly unresolved rather than silently changing
the reviewed cleanup. Focused Ansible syntax/source contracts passed. Transfer
paths, prerequisites and exclusions: [transfer manifest](../ops/role-tests/cleanup/TRANSFER.md).

### 2026-10-26 — Late upstream targeting decisions

User confirmed node preparation targets `all` and installation-only BIST remains
enabled. Updated site and docs; [transfer decisions](../ops/role-tests/cleanup/TRANSFER.md)
now record both choices. No join, service or hardware operations performed.

### 2026-10-26 — Portable source documentation

Removed private environment history, hostnames and experimental-only links from
copyable source documentation. Kept operational prerequisites and limitations.
Sphinx HTML build passed; external Python inventory was unavailable in sandbox.

### 2026-10-28 — Python CA audit in provisioning

Added [audit_python_ca](../roles/audit_python_ca/README.md), its bundled read-only
script and standalone playbook. The final site play imports the audit; reports
are printed before findings or incomplete checks fail provisioning. No package
or certificate remediation is performed. Full provisioning syntax, real Ansible
task fixtures for clean/finding/incomplete/error results (`changed=0`), public
certificate detection fixtures and source/link checks passed. No server audit or
production provisioning was run; scope and exclusions are documented in the role.

### 2026-10-28 — Retire FSP/VCC gRPC provisioning

Removed the gRPC installer from `site.yml` and its unused controller/proto/grpcurl
downloads. The [certificate cleanup](https://github.com/DragonLord-64/experimental-fhs-baremetal/blob/3ac370e/roles/remove_fhs_grpc/README.md) updates CA
trust, decodes the system bundle, stops/disables the two controller services and
removes their units, managed/legacy installations and matching root Poetry venvs
before deleting the FHS/runner venvs. Shared bitstreams, SDK and unrelated user
environments remain. Copied the latest official Ubuntu Python/CA package update
into site provisioning under `python_ca_updates`.

Full provisioning, cleanup and artifact-download syntax passed. A bounded
Ansible fixture used real file/find tasks with a service-manager stand-in:
controller paths were removed, shared/personal paths preserved, the second run
reported `changed=0`, and a failed service stop preserved controller data. Source
and documentation links passed. No VM or production run; real systemd remains
unverified. The personal gRPC certifi and shared virtualenv seed-cache findings
are outside this controller removal and remain for separate remediation.

### 2026-10-28 — Inline and tag certificate cleanup

Removed the cleanup role and moved its tasks and conditional systemd reload
directly into `certificate-update.yml`. Independent blocks now expose `update_ca`,
`verify_ca`, `remove_fhs_grpc`, `reset_venvs` and `refresh_snaps`. Existing cleanup
root overrides remain supported. [Commands and scope](../docs/src/playbooks/certificate-update.md)
replace the removed role documentation; the earlier role reference is pinned to
its original commit.

Provisioning/cleanup syntax and tag listing passed. The bounded file/service
fixture passed tagged cleanup, an unchanged rerun, preservation on a stop failure
and independently tagged venv reset. Source/link checks passed. No VM or production
execution; real systemd remains unverified.

### 2026-10-28 — Validate cleanup and explain certificate findings

Added the shared [Python CA audit](../roles/audit_python_ca/README.md) after
[certificate cleanup](../docs/src/playbooks/certificate-update.md). Both cleanup
and final provisioning validation run on tagged executions; skipping
`audit_python_ca` explicitly defers validation. Reports lead with the result and
numbered findings, affected environments, meanings and remediation guidance.
Package inventory and successful bundle checks follow; scope limits remain explicit.

Real certificate fixtures reproduced five findings across eight environments,
passed after bundle replacement and rejected an invalid bundle as incomplete.
Real Ansible task fixtures verified both tagged call sites and failure gates.
Full provisioning/cleanup syntax, tag listing and source/link checks passed.
No VM or production execution was performed.

### 2026-10-29 — Hardware BOM planning workbook

Added the [inventory planner](../outputs/hardware-bom-20261029/hardware-inventory-planner.xlsx)
with editable definitions, reusable recipes, unique role hierarchy, build/spares
totals, serial asset assignments and partial shipment tracking. All populated
records are illustrative. Stock snapshots and current assignments are manual;
the workbook does not synchronize NetBox or retain assignment history.

Formula checks covered shared quantities, zero overrides, new parts/roles,
missing components and partial receipts. LibreOffice recalculation verified the
example BOM and a changed recipe with one VCCU excluded. No hardware accessed.

### 2026-10-30 — Provisioning inventory and verified platform access

Split site group vars, selected current NetBox inventory explicitly and retained
official device-role targeting/runtime inputs. Added public CA distribution,
verified devpi/Elasticsearch ingress, new service endpoints, NetBox verification
and a Filebeat setup-only command using the selected device package. Removed
active role site paths/endpoints from generic defaults. Fixed Squid stale-PID
startup after container restarts. Usage docs follow the Bifrost quickstart;
deleted duplicate READMEs remain removed. No throughput tuning was included.

Existing `fhs-test` delivered-chart tests passed for HTTPS pip install/import,
Git proxy allow/deny and restart, APT transport and verified NetBox inventory/native
importer smoke. The delivered logging child chart passed same-package Filebeat
template/ILM setup without controller installation. Full importer tests retain
five baseline failures; broader legacy
live acceptance stops at its existing identity assertion. No full-suite or
production deployment claim. See [validation](../ops/security-provisioning/VALIDATION.md)
and [official copy prerequisites](../ops/security-provisioning/TRANSFER.md).

### 2026-10-30 — Copy-only official transfer helper

Added [the transfer script](../ops/security-provisioning/copy-to-official.py) for
sibling checkouts. It copies selected source changes, applies recorded deletions,
preserves the destination NetBox token/filters and host inventory, backs up
overwritten files and leaves official Git changes unstaged. A temporary-checkout
fixture verified dry-run, copy/deletion, preservation, backup and dirty-target
refusal. Source/link and whitespace checks passed; official was not modified.

### 2026-10-30 — Plain copy transfer

Replaced the transfer helper's history-dependent selection and merge/backup logic
with direct folder/file copies at the user's request. No Git inspection or
destination cleanup; matching files are overwritten, including NetBox inventory.
Old group-vars files still require manual removal. Source/link and whitespace
checks passed. Official was not modified.

### 2026-10-30 — Combined user and BittWare environment setup

The `manage_users` role now creates accounts, installs the selected system SDK
and activates/installs tools into the shared `/opt/venvs/fhs` and each managed
account's `.bw_venv`. GitLab runner and the existing local account are ordinary
inventory entries; SSH/password/group settings remain configurable. Site calls
the role after distribution access instead of separate users/venv/SDK/runner
steps. Task files separate accounts, system package and environment setup.

Disposable Ubuntu validation passed first installation, repeat installer skips,
ownership-drift repair and SDK-version upgrade for four personal environments
and the shared environment. Syntax, source boundaries and documentation builds
passed. Tests used a synthetic SDK, not proprietary packages or hardware; the
container was removed. See [results](../ops/role-tests/user-environments/VALIDATION.md).

### 2026-10-30 — Retired duplicate roles and explicit preflight

Removed the standalone venv/SDK/runner implementations. Their old main entry
points now stop with migration instructions; `manage_users` remains the single
site workflow. No active source play invokes the retired roles.

Added [preflight usage](../docs/src/playbooks/preflight.md) for selected
distribution, account/SDK and Filebeat inputs. It reuses input validation, reads
files and checks TCP/verified HTTPS without account, package or setup changes.
Credential contents are suppressed; input-only bootstrap is explicit. NetBox
inventory still requires working controller trust/token before the play starts.

The focused [fixture](../ops/role-tests/preflight/README.md) passed success with
zero changes, missing artifacts, invalid credential fields, TLS failures,
downgrade rejection, bootstrap and retired-entry-point cases. Input hashes stayed
intact. Syntax, source boundaries and documentation builds passed. CI and
dependency declarations were unchanged; temporary importer failures were not
repaired or rerun. No production deployment was performed.

### 2026-10-30 — Operator instructions without change-history assumptions

Reworked NetBox inventory/import/export instructions around file locations,
credential formats, variable assignments, URL prefixes and commands. Added
concrete user-key, Filebeat credential and HTTPS values examples. Core usage
guides describe the current setup; transfer history stays in experimental notes.
Recorded this writing rule in the repository instructions.

The documentation agent drafted the focused changes; parent review corrected
the requirements-file path and export inventory selection. Local source/link
checks and Sphinx HTML passed. No runtime or deployment changes were made.

### 2026-10-30 — Use the configured Vault password file

Verified that the official checkout retains the Bifrost Compose Vault password
file mount and environment variable, and its quickstart documents creating the
file. Removed interactive Vault password flags from documentation commands and
documented the existing Compose configuration in the NetBox inventory guide.

### 2026-10-30 — Explicit Ubuntu hardening membership

NetBox inventory selects `ubuntu24_cis_production` through the
`ubuntu24-hardening` tag independently of device role. Updated inventory and
site-playbook usage instructions. Five local expression cases passed: tagged
FPGA/other servers included; untagged FPGA, legacy context and missing tags
excluded. Source/link and whitespace checks passed. No deployment was run.

### 2026-10-30 — Clarify supported FSP/VCC services

Corrected operator documentation: FSP/VCC gRPC services remain supported.
Certificate-update is one-off security remediation, and its removal block
requires separate controller redeployment. Documented that the current site
playbook does not include the installer without calling the role historical.
Five documentation/link checks and whitespace checks passed; no runtime changes.

### 2026-10-30 — Name Kubernetes node preparation explicitly

Renamed `setup_fhs_node` to `setup_k8s_node`, including the role tag, documentation
include and executable references/fixtures. The site play retains its `fhs_node`
umbrella tag, which also includes BIST. Corrected the role README's site target
 to `device_roles_fpga-host-server`. Focused Ansible syntax and source/link checks
passed; no host configuration was applied.

### 2026-10-30 — Remove umbrella tag and obsolete transfer paths

Removed the `fhs_node` play tag; Kubernetes preparation and BIST retain their
individual role tags. The plain transfer script removes the destination's old
`roles/setup_fhs_node/` directory and its obsolete documentation include after
copying. A disposable transfer check passed with obsolete paths present and on
rerun without them, preserving an unrelated file. Tag-selection source checks,
source/link checks and whitespace checks passed. No deployment was run.

### 2026-10-30 — Keep the gRPC role introduction about its use

Replaced site-playbook and security-remediation commentary in the gRPC role
README with its installation purpose and a NetBox tag/service selection table.
Removed standalone Poetry role retirement commentary from its prerequisites.
Documentation/link and whitespace checks passed; no runtime changes.

### 2026-10-30 — Record the user's documentation preferences

Recorded current-system, operator-first documentation preferences in
[the documentation note](documentation-preferences.md), linked from the wiki
index and repository instructions. Includes concrete configuration/command
examples, role-focused scope, deployed-environment context and preservation of
intentional README deletions. Source/link and whitespace checks passed.

### 2026-10-30 — Delete obsolete standalone user/SDK roles

Deleted the retired manage_venvs, manage_bittware_sdk and manage_gitlab-runner
role placeholders and documentation includes. Updated SDK guidance to
manage_users and removed the obsolete migration-message fixture cases.
The transfer script deletes those destination roles/pages as well as the old
Kubernetes role name. Disposable transfer and rerun checks passed, preserving
active users/gRPC roles; source/link and whitespace checks passed.

### 2026-10-30 — Internal HTTP for the trusted development LAN

The user accepts HTTP for internal platform/provisioning endpoints; HTTPS may
be enabled later. Removed proposed devpi/Elasticsearch DNS names and mandatory
TLS/CA prerequisites. Updated NetBox, pip and Filebeat inventory, validation and
operator docs while preserving upstream HTTPS checks, package signatures and
private credential storage. Optional future TLS support remains available.

Scoped delivered-chart upgrade, real HTTP pip install/import, setup-only
Filebeat, authenticated NetBox API/inventory and native importer check mode
passed on the existing lab. Focused preflight, Helm render/lint, syntax and docs
checks passed with existing Grafana/external-inventory warnings. See
[validation and boundaries](../ops/security-provisioning/VALIDATION.md#development-http-decision--2026-10-30).

### 2026-10-30 — Export shared platform secrets and endpoints

Added a local exporter beside the Helm deployment script. It checks service
connectivity, registers/reuses the chart's NetBox token and writes
platform-secrets.yml plus platform-endpoints.yml. No rotation, automatic copying
or encryption. Ansible inventory/importers and Filebeat share the Vault secrets;
distribution/monitoring read exported endpoints. Machine paths stay in inventory.
The standard NetBox plugin's API URL remains the one manual inventory assignment.

Actual cluster export/repeat, Vault inventory, Filebeat setup, publishing-only
render and native importer check mode passed. Restored temporary lab mappings.
The source transfer script excludes generated export files. See
[validation evidence](../ops/security-provisioning/VALIDATION.md#shared-platform-handoff-files--2026-10-30).

### 2026-10-30 — Copyable platform password lookups

Added direct kubectl/base64 commands for NetBox, Grafana, Elasticsearch/Kibana
and Filebeat writer passwords to the copyable platform chart README, linked
from the platform entry page. Checked key names against the credentials template;
documentation/link and whitespace checks passed. No passwords were retrieved.

### 2026-10-30 — Remove separate-release platform source

Removed the eight standalone platform values files, old independent-release lab
launch/preparation/smoke scripts and their overlays. Kept the single-release
chart, provisioning overrides and current importer/umbrella checks. Removed
legacy-launcher regression cases and added provisioning-values coverage beside
the existing delivered-chart check. Historical results remain; citations to
removed source now use the last containing Git revision without changing the
recorded events.

The copy script removes those eight old platform files in the destination.
Ten umbrella tests, two NetBox render tests, disposable copy cleanup/rerun and
source/link/whitespace checks passed. No running release, PVC or stored test
data was removed.

### 2026-10-30 — Normalize NetBox compare request URLs

The exported NetBox base URL includes a trailing slash. Four direct URI requests
in compare.yml appended another slash before api, producing a 404 although native
helpers succeeded. Reproduced 404 for the double-slash custom-field URL and 200
for the normalized URL on the existing fhs-test NetBox. All four corrected
requests passed through actual Ansible URI tasks for zero, one and repeated
trailing slashes (12 HTTP reads). No hardware or inventory writes were performed.
Private fixture/logs remain under fhs-security-20261030/url-check on dragonvm.

### 2026-10-31 — Import Bifrost servers using controller-side IPMI

Added [the Bifrost adapter](../playbooks/netbox/bifrost_import.yml), reusing node
OS/BMC addresses and credentials without another bootstrap inventory. It installs
ipmitool on the controller, reads FRU and BMC metadata through bounded lanplus
commands, and retains the native SSH/component/topology stages. Remote FRU
failure or an absent unambiguous system serial stops the host before writes.
Passwords use environment variables and suppressed credential-task output.

Six focused unit tests and Ansible syntax checks passed. Against the existing
fhs-test chart NetBox, a synthetic BMC client exercised initial import, stable
identity on a Vault-encrypted repeat, rejected credentials and missing serial.
No physical BMC or target server was contacted; network IPMI compatibility still
needs verification on the deployment network. Private fixture logs are under
fhs-bifrost-ipmi-check/private on dragonvm. Sphinx built successfully; external
Python inventory fetching was unavailable, and a clean build also reported an
existing platform export-anchor warning. Source/link and whitespace checks passed.

### 2026-10-31 — Keep controller IPMI delegation local

Explicit localhost inventory could retain SSH transport when the importer
switched to its SSH server play. FRU and both BMC metadata tasks now explicitly
select local transport for localhost delegates, retaining SSH for an explicitly
remote delegate. A regression fixture declares both inventory hosts as SSH to
unreachable documentation addresses and runs the actual three IPMI tasks with a
synthetic client. All three execute locally and parse their results successfully.
Seven focused tests and wrapper syntax validation passed. No physical BMC or
NetBox changes were needed for this transport-only correction.

### 2026-10-31 — Running Bifrost environment diagnostics and CA patch helper

Added scripts/patch-bifrost-environment.py with read-only diagnostics, explicit
CA/pip/certifi updates and a separate release-constrained pyOpenSSL/cryptography
repair. It checks the GEN_EMAIL import path, records private package-version
snapshots, authenticates the pip bootstrap wheel using the Python security team's
published SHA256 and never restarts services or replaces containers. The transfer
script includes it; deployment operations show usage and container-state limits.

Five focused tests passed with package commands mocked; a real read-only probe
against an incomplete local venv correctly reported missing packages and returned
failure. Source/link checks and a disposable transfer passed. No deployed Kolla
environment was patched and no rebuild or database migration was performed.
Rebuilding remains separate work: the present Compose mounts do not explicitly
persist the Ironic database/config, and IPA/OS image trust requires its own update.

### 2026-10-31 — Correct Bifrost patch diagnostics for overlapping distributions

Operator output showed successful certifi installation followed by an older
reported version. Fixed last-wins distribution enumeration to use the active
metadata lookup precedence and display relevant installation locations. Replaced
the obsolete hardcoded ironic.cmd.dbsync import with loading the installed
ironic-dbsync entry point without invoking it. Six focused checks passed,
including real duplicate dist-info precedence and a newer Ironic entry point.
The reported pyOpenSSL/cryptography dependency conflict remains a separate real
repair requirement; no deployment package updates were run here.

### 2026-10-31 — Include jwcrypto in constrained Bifrost environment repair

The repaired cryptography/pyOpenSSL pair exposed an installed jwcrypto requirement
for a newer cryptography. Repair now resolves all three together under local
constraints. It checks the two installed constraints locations, skips broken
links and stops before package changes if missing/unreadable or conflicting.
Explicit --constraints remains available. Diagnostics also report jwcrypto.
Eight focused tests passed, including fallback past a broken link, conflict
rejection and a combined constrained pip transaction. Live deployment updates
remain operator-run; no service restart or database changes were performed here.

### 2026-10-31 — Record the operator's discovery-to-provisioning vision

Captured the confirmed TerraBox workflow, explicit target/cleaning gates,
NetBox review ownership, shared deployment profiles, mixed Nexus/FHS provisioning,
optional detailed inventory and YAML fallback in provisioning-workflow-vision.md.
Mapped existing code to implementation gaps and ordered acceptance slices.
Indexed the note and recorded the decision. Documentation only: no runtime,
inventory, network, device or lifecycle changes. CLI examples are proposals.

### 2026-10-31 — Stop Bifrost configuration from reinstalling a drifting runtime

Traced the delivered Kolla/Bifrost installer: prep defaults to master/source
updates and install.yml reinstalls Ironic. The cached release has Ironic 35.1.1,
whereas the operator reported 39.1.0.dev114. Configuration must preserve the
installed runtime instead of silently mixing releases or downgrading its DB.

Added the patch helper's guarded configure action, configuration-only defaults
in experimental target vars, a guarded launcher and constrained Dockerfile Python
installs with the pip/certifi security pins. Optional --build-images retains the
mounted image settings for initial setup; normal configure reuses existing images.
The focused transfer copies six Bifrost-related files, leaves destination target
vars/unrelated edits alone and performs no legacy cleanup.

Reproduced GEN_EMAIL in a disposable cached Kolla container, ran the real repair,
passed pip/import diagnostics, obtained real Ironic API HTTP 200 and ran the actual
schema-upgrade command against disposable SQLite. Constrained DIB/tooling installs
also passed subsequent diagnostics. The real role fixture skipped source/package
changes with changed=0. Twelve focused unit tests, source/link/whitespace checks,
launcher shell syntax and the focused transfer passed. Sphinx built with existing
anchor warnings and unavailable external Python inventory. No production system
was modified; the full image build/configuration and production MySQL migration
remain unverified. The disposable test container was removed. See
ops/role-tests/bifrost-environment/VALIDATION.md for evidence and scope.

### 2026-10-31 — Make the focused Bifrost transfer the default

Corrected the transfer default to match the requested current-work-only copy.
Running copy-to-official.py without a scope flag now copies six Bifrost files;
--full explicitly selects the prior broad transfer/cleanup. --bifrost-only remains
an alias. Disposable default/full checks passed: default preserves unrelated
inventory/docs/role edits and cleanup candidates; full retains its cleanup.

### 2026-10-31 — Physical auto-discovery and hwmanage interface agreed

The operator supplied saved physical Ironic inspection showing
auto_discovered=true, a system serial, BMC address and UEFI PXE interface MAC.
This confirms the observed unknown-node discovery path; FRU model/provenance and
the future NetBox bridge still require validation. No raw capture or credentials
were added. Updated [workflow vision](provisioning-workflow-vision.md) with the
approved hwmanage groups, native YAML fallback, fixed runbooks, explicit metadata
cleaning and command independence requirements. Runtime implementation is tracked
separately; this note does not claim end-to-end deployment passed.

Implementation scope and acceptance are tracked in
[experimental issue #17](https://github.com/DragonLord-64/experimental-fhs-baremetal/issues/17).
The targeted transfer was exercised in disposable destination folders: feature
files copied, unrelated roles/group vars/platform/docs preserved, caches excluded,
explicit six-file Bifrost scope retained and full-transfer cleanup retained.

### 2026-10-31 — hwmanage implementation and focused integration

Delivered the scoped hwmanage interface, portable native inventory bridge, initial
NetBox import playbook, optional detailed site inventory, fixed runbooks and
configuration/check helpers under issue #17. Full-provision performs deployment
prerequisite checks before metadata cleaning. Discovery import snapshots selected
UUIDs before running the controller-local import playbook. Commands remain
independent through lazy application dependencies; YAML remains an explicit source.

The preliminary pipeline ran 18 tests with one native inline-extra-vars case
skipped; that case passed separately with Ansible installed. After final
preflight/import changes, the native focused suite passed 26 tests with no skips,
and the updated initial-import playbook passed native syntax validation. Real
Ansible syntax checks for provisioning/import/wait, native site-vars assertions
and offline YAML-pattern selection passed. Lab integration ran the actual
controller import task and native SDK against synthetic Ironic HTTP/FRU evidence
and the existing chart's real NetBox: ten assertions passed. These results do not
prove controller package installation or physical cleaning, boot, inspection,
adoption or OS deployment; hardware lifecycle operations were not exercised.
See [focused validation](../ops/role-tests/hwmanage/VALIDATION.md) for commands,
observed evidence and limits.

Final lab rerun passed 11 assertions, including wrapper-to-native-playbook UUID
selection and environment paths. Nine additional focused checks for root-device
criteria and native password compatibility passed. Physical lifecycle and
controller package-installation limits above still apply.

### 2026-10-31 — hwmanage PATH installer

Added [install-hwmanage.sh](../scripts/install-hwmanage.sh) to link the checkout's
command into `/usr/local/bin`, with an optional bindir. The
[operator guide](../docs/src/playbooks/hwmanage.md) retains `/provision` for
Ansible configuration and documents installation after container recreation.
Both targeted and full [transfer scopes](../ops/security-provisioning/copy-to-official.py)
include the executable installer; no image rebuild is needed.

Focused disposable-directory checks passed: resolved symlink, repeat install,
PATH `hwmanage --help`, refusal to replace a regular file, unrelated symlink or
dangling symlink, and executable installer content in targeted/full copies.
These cover runtime/link and copy behavior beyond the controller's syntax/policy
checks, which are left to the controller. No container or hardware operations
were run; `/usr/local/bin` on the host was not changed.

### 2026-10-31 — hwmanage import diagnostics

[hwmanage](../scripts/hwmanage_lib/common.py) now relays Ansible output while it
runs and prints failed application output. `-v` exposes other application output
and increases Ansible verbosity. The [importer](../playbooks/netbox/ironic_minimal.py)
prints unexpected exception tracebacks; its playbook no longer censors the
command result. Other tasks' explicit secret protection remains in place.
The [usage page](../docs/src/playbooks/hwmanage.md) documents private handling
of output, which can contain credentials or inventory data.

The [copy helper](../ops/security-provisioning/copy-to-official.py) adds
`--diagnostics-only` for existing official hwmanage checkouts; default/full
copies already include these files. No official checkout was changed here.

Focused hwmanage contracts: 31 tests passed, one skipped. New coverage checks
stdout/stderr separation, failure/timeout private files, verbosity parsing and
exact diagnostic copy content with unrelated destination content preserved.
Ansible import syntax passed using a writable `/tmp` local-temp override after
the default home temp path was blocked by the sandbox. `git diff --check` passed.
No lab or physical import was run; the photographed import's cause remains
unconfirmed until the updated command exposes its error.

### 2026-10-31 — split NetBox endpoint and token loading

The [wrapper connection loader](../scripts/hwmanage_lib/inventory.py) now supplies
`platform-endpoints.yml`'s URL to the shared credential loader before validation.
This accepts the actual platform export: endpoint in the public endpoint file,
token in protected `platform-secrets.yml`. Previously the loader required a URL
in secrets before applying the endpoint override. Legacy combined credentials
remain supported when the endpoint file is absent. Override URLs now pass the
same validation as URLs loaded from secrets.

The [focused copy scope](../ops/security-provisioning/copy-to-official.py) includes
both affected loaders. The operator guide documents the separate files.
Hwmanage suite: 33 tests run, one skipped; transfer suite: three passed.
New cases cover split plain/Vault credentials, invalid endpoint rejection and
legacy combined files. `git diff --check` passed. No lab or physical import run;
the site deployment still needs the updated files and an import retry.

### 2026-10-31 — hwmanage application folder and tracked import settings

Moved the command and package into [hwmanage/](../hwmanage/README.md), keeping
[scripts/install-hwmanage.sh](../scripts/install-hwmanage.sh) as the installer.
It migrates the old checkout-owned PATH link while refusing unrelated links.
Native NetBox playbooks stay independent under `playbooks/netbox/`.

Non-secret [import.yml](../hwmanage/import.yml) is now the default import settings
file. Site/role/device-type IDs are unset pending operator selection; the FRU ID
and approved onboard interface names remain explicit. `HWMANAGE_IMPORT_DEFAULTS`
still selects a local file. Credentials remain outside the repository.
Updated docs, focused/default/full transfer paths and acceptance entry points.
Copying retains old destination source files; reinstalling selects the new app.

Validation: 35 focused tests passed with Ansible installed, import playbook syntax,
installer shell syntax, direct command/importer help and `git diff --check` passed.
The existing lab chart's services were Ready. After replacing an expired local
forward, [lab acceptance](../ops/role-tests/hwmanage/VALIDATION.md) passed all 11
assertions through the relocated wrapper/native importer; synthetic objects and
the temporary forward were cleaned up. No physical hardware was contacted.

### 2026-10-31 — hwmanage under Bifrost infrastructure

Moved the application and tracked settings to
[bifrost-infra/hwmanage/](../bifrost-infra/hwmanage/README.md), updated repository
root resolution, import paths, transfer scopes and the existing scripts installer.
The installer migrates links from either previous location. Compose now mounts
this folder at `/provision/bifrost-infra/hwmanage`. Existing containers can use
the documented `docker cp` procedure without an image rebuild or recreation;
source updates require another copy until the new mount is active.

Validation: 35 focused tests passed, including both link migrations, copied files
and default settings. Ansible import syntax, shell syntax, Compose YAML/mount
inspection and whitespace checks passed. All 11 native importer/wrapper lab
assertions passed against the existing healthy chart in explicit `fhs-test`
context, with synthetic fixture cleanup and temporary forward removal. No
physical hardware, host lifecycle or user container operations were performed.

### 2026-10-31 — use the existing scripts mount for hwmanage

At the user's request, moved the application to
[scripts/hwmanage/](../scripts/hwmanage/README.md) and removed the extra Compose
mount. The existing scripts bind mount exposes source updates immediately;
no Docker copy, image rebuild or container recreation is needed. The installer
remains `scripts/install-hwmanage.sh` and migrates links from previous locations.
The copy helper preserves the original file-form command as `hwmanage.legacy`
when upgrading an older checkout to the new directory layout.

Validation: 35 focused tests passed, including old-link migrations and transfer
from the original executable layout; Ansible syntax, shell syntax and whitespace
checks passed. All 11 synthetic native importer/wrapper assertions passed against
the existing healthy chart in explicit `fhs-test` context. Fixture objects and
the temporary forward were cleaned up; user containers were not changed.

### 2026-10-31 — continue imports after individual node failures

The [minimal importer](../playbooks/netbox/ironic_minimal.py) now reports each
failed UUID and continues other nodes after observation, identity-conflict or
write failures. Duplicate serial/BMC observations still reject all implicated
nodes before writes. Successful writes are retained; any failures produce a
nonzero exit and completed/failed counts. A failed write can leave partial
objects; diagnostics and repeat identity checks remain necessary.

Boot qualification errors include the inspected interface name for review in
`scripts/hwmanage/import.yml`. Registration `node sync` remains a database/port
reconciliation command, not inspection collection; the operator guide says so.

Validation: 37 focused tests passed, including mixed read/conflict/write failures
with a successful later node and rejection of every duplicate owner while an
independent node succeeds. All 11 existing native importer/wrapper lab assertions
passed against the healthy chart in explicit `fhs-test` context. Synthetic objects
and the temporary forward were cleaned up. Whitespace checks passed; no physical
hardware or deployed-node state was changed.

### 2026-10-31 — automatic provisioning interface selection

The user confirmed motherboard classification is not required for provisioning
port selection. The [minimal importer](../playbooks/netbox/ironic_minimal.py) now
uses the unique inspected boot-MAC match without mandatory `onboard_interfaces`.
It still rejects absent/invalid boot MACs, ambiguous matches and missing interface
names. Optional `provisioning_interface` constrains the expected name and fails
on mismatch; null enables automatic selection. Old onboard settings are unused.
Tracked settings and operator documentation explain this and the NetBox object
IDs/FRU selector; existing devices retain their site/role/device type.

Validation: 37 focused tests passed, including a representative multi-NIC record,
automatic selection without an onboard flag, expected-name mismatch, duplicate
MACs and missing/invalid boot MACs. All 11 native importer/wrapper assertions
passed against the existing healthy chart in explicit `fhs-test` context with
no onboard setting in the synthetic fixture. Synthetic objects and the temporary
forward were cleaned up. Whitespace checks passed; physical hardware is untested.

### 2026-10-31 — central hwmanage controller YAML

Added [config.yml](../scripts/hwmanage/config.yml) for controller connections,
credential-file paths, inventory selection/site variables, Bifrost playbooks,
import defaults, timeouts and system checks. It replaces `import.yml`; paths
resolve relative to the selected config. `--config`, `config show` and
`config validate` expose selection, effective values and path/schema checks.
The wrapper translates YAML into native-tool environment settings within a
restored command context; operators need no shell exports.

A small [Ansible lookup](../scripts/hwmanage/lookup_plugins/hwmanage_config.py)
shares configuration and Vault password access with direct playbooks. Shared
path group vars and NetBox defaults retain their existing variable names.
At the user's request, native NetBox inventory keeps its plain copied endpoint;
only its credential-file lookup uses central config. No inventory adapter was
retained. Roles and provisioning group vars remain otherwise unchanged.
The copy helper includes config, lookup registration and its shared consumers.

Validation: 40 focused tests and three transfer tests passed; import playbook
syntax and whitespace checks passed. Direct Ansible test verified selected
config, shared group-var paths and decryption using a YAML-selected Vault password
file. Final live lab acceptance passed 12 assertions against the healthy existing
chart in explicit `fhs-test` context: direct import, wrapper plan, native NetBox
inventory with copied endpoint and central credential path, identity/persistence
and conflict protection. Fixtures and temporary forward were cleaned up. An earlier
trial exposed empty Vault-password environment handling, corrected before the
final pass. Physical hardware remains untested.

Read-only official comparison: `development2` at `f13c26a` (no `development-2`
branch). Existing roles, platform content and controller-side IPMI tasks match
our pre-change source. Official retains the legacy flat `group_vars/all.yml` and
`group_vars/device_roles_fpga-host-server.yml` alongside split directories; the
copy helper retains them. Official discovery group vars and `bootstrap_inv.yml`
are also retained by the helper. Full/Bifrost-only scopes overwrite the differing
`patch-bifrost-environment.py`; its official security update exists here, but
our version additionally changes constraints/runtime handling and configuration.
The central-config transfer intentionally changes ansible.cfg, shared paths and
the native inventory's token lookup. No official checkout edits, reconciliation
or pushes were made; these differences were flagged for user review only.

### 2026-10-31 — platform deploy and export shortcut

Added [platform/deploy.sh](../platform/deploy.sh): invoke the existing Helm
upgrade/install helper, then the existing platform exporter after success.
Release `mid-cbf-hw` and namespace `hw-management` match official development2's
deployment helper. It uses the current Kubernetes context, existing provisioning
values and the exporter's normal two-file output directory. No extra options or
configuration layer were added. Updated the default transfer manifest and brief
operator instructions; full transfer already includes the platform directory.

Validation: shell syntax and whitespace passed. Disposable command stand-ins
verified Helm/export ordering, release/namespace/readiness arguments, stopping
before export on Helm failure, invocation outside the repository and rejection
of unexpected arguments. A disposable default copy retained helper content and
executable mode. No real Helm operation, secret export or user container change
was performed; the underlying deployment/export implementations are unchanged.

### 2026-10-31 — NetBox names in new-device defaults

[Import defaults](../scripts/hwmanage/config.yml) now accept existing NetBox site
and device-role names or slugs, and device-type model names or slugs. The importer
resolves exact matches to IDs only when creating a device. Missing or ambiguous
matches fail before that node's writes; every matching ID is considered rather
than choosing the first result. Numeric values remain compatible. Existing device
assignments are preserved, and unrelated commands no longer reject string defaults.
Documentation uses human-readable examples instead of requiring ID lookup.

Validation: 41 focused tests passed, covering names/slugs/models, ambiguity,
missing matches and unrelated command config loading. All 12 native importer/
wrapper/inventory assertions passed against the existing healthy chart in explicit
`fhs-test` context; the live fixture supplied site name, role slug and type model.
Synthetic objects and the temporary forward were cleaned up. Whitespace checks
passed. No physical hardware or official checkout was changed; the existing copy
manifest already includes all changed application/importer files.

### 2026-10-31 — remove obsolete import YAML during transfer

The source `import.yml` was already removed when central config landed. The
[copy helper](../ops/security-provisioning/copy-to-official.py) now removes old
application-owned import settings after successful default, diagnostics-only or
full transfers, including the prior application locations and Bifrost template.
External site/resource files and the Bifrost-only transfer remain untouched.

Validation: 42 focused tests passed. New disposable default/diagnostics copy
checks verify all four obsolete paths are removed, central config is delivered,
and an external resource override is preserved. Whitespace checks passed.
No official checkout or lab deployment was changed.

### 2026-10-31 — inventory templates and ready-to-paste NetBox JSON

Moved hardware-management templates from `bifrost-infra/templates/` to
[inventory/templates/](../inventory/templates/). The deployment profile is now
JSON for direct NetBox Config Context entry. Image URL/checksum, driver, boot,
RAID and subnet/DNS values copy the existing Bifrost baremetal group vars; the
root-disk size hint copies the existing per-node inventory convention. No login
values were copied from per-node inventory. Native node YAML shares the actual
deployment defaults, while its per-node identity fields remain illustrative.

The shared `> 900` root-disk hint matches both previously supplied SYS1412 NVMe
disks; docs explain a per-device serial selector to narrow it. Updated copy
scopes transfer templates and remove old template paths after successful copies.

Validation: 42 focused tests passed, including new template content transfer and
old-location cleanup. JSON parsed and its deployment fields matched existing
Bifrost source values; credential-field and whitespace checks passed. This copies
the configured checksum, not a new image-byte verification. No deployment or
hardware operation was performed.

### 2026-10-31 — correct native Ironic port ownership queries

The user confirmed NetBox already holds the discovered Ironic UUID. Native SDK
inspection found two issues: ownership checks requested summary port responses,
and node-port filtering used `node_uuid` rather than an SDK-supported query key.
[Reconciliation](../scripts/hwmanage/hwmanage_lib/ironic.py) now requests detailed
ports and uses `node=UUID`, with a non-null owner alias fallback and actionable
owner/selected-UUID errors. Existing UUID/name resolution and ownership rejection
are retained. No MAC-based takeover or missing-link fallback was shipped.

Validation: 43 focused tests passed. All 14 chart/importer/native-SDK acceptance
assertions passed with a linked unnamed synthetic node, summary responses that
omit ownership, and an unrelated node's port. Plan performed no updates; sync
renamed the linked node through native PATCH without UUID changes or new ports.
The healthy existing chart was inspected with explicit `fhs-test`; fixture objects
and temporary forwarding were cleaned up. Whitespace checks passed. Actual user
port ownership remains unverified until retry; no physical node was changed.

### 2026-10-31 — serial-named Ironic registrations, NetBox authoritative

At the user's request, the wrapper now uses the NetBox product serial as the
Ironic node name. NetBox device names remain operator/Ansible targets. Enrollment
finds or creates that serial name; Ironic UUIDs are generated/resolved internally
and no longer read from NetBox. Bifrost receives the serial name and any runtime
UUID; native lifecycle commands use the node name. Duplicate selected serials
and MAC ownership conflicts fail without claiming or deleting registrations.
Existing unnamed/old-named discoveries need explicit operator rename or cleanup.
No saved-inspection serial lookup is performed just to reconcile an existing node.

The minimal importer matches NetBox by physical serial/default name, no longer
creates or updates an `ironic_uuid` custom field, and accepts rediscovery under
a different Ironic UUID. Existing legacy metadata is ignored and retained rather
than deleted globally. Native Bifrost export no longer falls back to that field.
Credential overrides prefer product serial/NetBox name; direct discovery imports
retain compatibility with legacy UUID-keyed credentials. The copy helper includes
the changed native exporter. Updated operator docs and template comments.

Validation: 47 focused and three transfer tests passed; native Bifrost-export
playbook syntax and whitespace checks passed. All 14 existing chart/importer/
native-SDK acceptance assertions passed in explicit `fhs-test` context. They
verified serial-name lookup without a NetBox UUID, no UUID persistence on new
imports, retained names/primary IP/tags/status, rediscovery and conflicting serial
rejection. Unit coverage verifies fresh enrollment without a supplied UUID,
name-addressed lifecycle commands and serial-named ephemeral Bifrost inventory.
Fixtures and temporary forwarding were cleaned up; no physical node or official
checkout was changed. Full physical deployment remains untested.

### 2026-10-31 — name discoveries during import and sync

Import now checks the verified product serial's Ironic name before writes, then
names the existing discovery after successful NetBox apply. It preserves the
registration and ports and creates no NetBox UUID link. Sync/enrollment also
resolve a missing serial name through existing provisioning port ownership and
update that same registration, including unnamed/old-named discoveries. Multiple
owners or conflicting serial-name ownership fail; no ports move and nothing is
deleted. Import/sync plans rename neither system. A post-NetBox rename failure
is reported and can be retried against the existing device.

Validation: 49 focused tests and all 16 native chart/importer/SDK acceptance
assertions passed in explicit `fhs-test`. New checks cover import plan with zero
writes, verified-serial naming during import, sync plan without writes and sync
naming without new registrations/ports. A test-harness negative lookup cache
initially hid the externally created fixture device; the harness now clears that
cache and discovers owned objects during cleanup. The retained synthetic fixture
and parents were removed before the successful rerun; final cleanup and temporary
forward removal completed. Whitespace checks passed. No physical hardware or
user deployment was changed; the existing copy manifest includes changed files.

### 2026-10-31 — minimum BMC/port fallback without saved inspection

The user clarified the required IP is the BMC IP, not the running OS address.
When saved Ironic inventory is absent or boot-interface details are incomplete,
the minimal importer uses one registered PXE port plus controller-side BMC FRU
verification. It derives the BMC IP from saved data or the Ironic IPMI/Redfish
connection. No SSH, inspection ramdisk, deployment transition or power command
is used. Authentication/service failures are not masked as missing inventory.
Missing or ambiguous PXE ports still fail per node.

Unknown OS interface names use a clearly synthetic `provisioning` NetBox name,
or the configured expected name. Existing matching NetBox interface names are
retained. The BMC IP remains out-of-band; no Linux primary address is inferred.
Normal verified-serial naming runs on fallback success too, including replacing
an old Ironic name while preserving registration and ports. Existing copy scopes
already include all affected application/importer files.

Validation: 51 focused tests passed, covering missing/partial/null inspection
interfaces, Redfish BMC address extraction, FRU identity, disabled/ambiguous PXE
ports, authentication errors and existing interface-name preservation. All 18
chart/importer/native-SDK acceptance assertions passed against the healthy chart
in explicit `fhs-test`, including HTTP-404 fallback and old-name correction.
Final null-interface handling was additionally covered by the focused suite.
Synthetic objects and temporary forwarding were cleaned up. Whitespace checks
passed. Real BMC transport and physical hardware remain untested.

- 2026-10-31: Full Linux interface inventory now adopts the minimal import's
  tagged temporary `provisioning` interface by MAC, renaming it in place before
  detailed writes. Preview permits this planned ownership match without writes;
  existing-name collisions still fail. See
  [interface adoption](../playbooks/netbox/library/fhs_provisioning_interface.py).
  Validation: 51 wrapper tests, three transfer tests, lab playbook syntax and
  21 native lab acceptance assertions passed, including rename preview,
  relationship preservation and repeat-run idempotence. Physical hardware was
  not exercised.

- 2026-10-31: Corrected BMC credential loading to accept the existing platform
  `redfish.credentials.default.redfish.username/password` structure in discovery
  import and Bifrost export. Earlier defaults/device overrides remain supported.
  Updated the copyable template and usage example. Validation: 52 wrapper tests,
  three transfer tests and an Ansible credential-mapping fixture passed.
