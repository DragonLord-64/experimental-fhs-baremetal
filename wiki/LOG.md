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

- Corrected two review findings against [the authenticated Elasticsearch readiness probe](../platform/charts/elasticsearch-kibana/templates/elasticsearch.yaml) and [active Poetry tasks](../roles/manage_poetry/tasks/main.yml): health checks use the container's protected password; Poetry documentation describes installation only, its existing virtual environment and the site wrapper tag. Strict Sphinx 7.4.7 `-E -a -b html -n -W --keep-going` passed using the external documentation tools after allowing the public Python inventory fetch; sandbox DNS had blocked that fetch. Poetry wrapper syntax/task selection and health-command shell syntax passed without contacting targets. Loopback Playwright checks rendered both Mermaid diagrams and representative built pages without page errors; private captures remain under `/tmp/fhs-docs-*`. No runtime service, provisioning or wake-script checks were performed. Independent review remains the controller's next stage.

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
- Corrected existing lab NetBox web resources to two workers and a 2 GiB limit after a concurrent management command caused OOM. [Concurrent API/management validation](../ops/platform/netbox-resource-test.py) passed 62 API requests without OOM or pod restarts; 186 devices remained and logging stayed stopped. See [platform operations](../ops/platform/README.md).
- Fixed the portable static Grafana demo in commit `62422f12ddb69551bc1a13ded1488dc1a40d3d15`. Rack switch summaries now include member faults; mesh available capacity shows zero on failed links and varied deterministic percentages on healthy links. Configured line rate and physical hardware states remain separate. Nineteen unit/HTTP checks, fresh independent review and 14 real Compose/Grafana/browser/portability gates passed on dragonvm. The final ZIP with refreshed screenshots also passed extraction/launch/query checks; ZIP and evidence are under `/tmp/fhs-grafana-static-fix-evidence/`. Existing NetBox and Kubernetes workloads were not changed by this demo run.
- Added a portable [single-release platform chart](../platform/charts/fhs-platform/README.md) with bundled dependencies, configurable namespace/URL prefix, fresh PostgreSQL/Valkey, optional copied external database and six provisioned runtime dashboards. [Eight real render/mock-API checks](../ops/platform/umbrella/README.md) passed, including upgrade credential preservation and actual dashboard unpacking. Manifests contain no cluster-scoped configuration resources or external Services; existing storage/ingress and capacity still require local checks. No hardware cluster was accessed or deployment performed; independent review is next.
- Fresh independent review of the [portable chart](../platform/charts/fhs-platform/README.md) found no actionable issues. Seven checks passed independently; its sandbox blocked only the loopback mock, which passed in the full eight-case implementation run with permission. The cached pinned Grafana image also verified init/probe tools and prefix substitution in a temporary UID-472 container with no network or host mounts and a read-only root. The standalone packaged chart rendered and passed manifest acceptance. Hardware login, routing/TLS, storage binding, migrations, telemetry and shared capacity remain unverified.
- Corrected the [portable chart's NetBox launcher](../platform/charts/fhs-platform/values.yaml) to serve static assets under the shared URL prefix, retaining initialization and its other Granian settings. Earlier manifest checks missed the pinned image's hardcoded `/static` route. The [new launcher regression](../ops/platform/umbrella/README.md) failed before the fix and passed for five prefixes afterward; all nine umbrella tests, six logging tests and both chart lints passed. The actual pinned image served four JS/CSS assets with HTTP 200 for all five prefixes in an isolated UID-1000 container on `dragonvm`, bypassing database initialization for that check. No hardware deployment, migrations, ingress/TLS or browser verification was performed; independent review is next.
- Fresh independent review of the NetBox static-route fix found no actionable issues. It verified the pinned entrypoint always initializes before executing the launcher, all five prefix cases and existing logging/lint checks; its sandbox blocked only the loopback mock already passed in the implementation run. A normalized before/after Helm render changed only `Deployment/fhs-netbox`. The fix is published to the private experimental `development` branch; hardware ingress and browser confirmation remain pending.
- Added the [upstream-documented media affinity](../platform/charts/fhs-platform/README.md) to the regular chart values: NetBox web, worker and housekeeping share a node by chart/release/component labels in the same namespace, retaining the original `ReadWriteOnce` PVC and no fixed node. The [render regression](../ops/platform/umbrella/README.md) failed before implementation; all ten umbrella tests passed with loopback permission and both chart lints passed afterward. Documented removal of the existing temporary web node selector after upgrading. No cluster deployment, multi-node scheduler or CSI attachment test was performed; independent review is next.
- Fresh independent review of the NetBox media affinity found no actionable issues. It verified the pinned chart's documented pattern, rendered label scope and self-matching startup, disabled-worker case, and post-upgrade removal of only the temporary hostname selector. The focused regression passed independently; full-suite and lint evidence are recorded above. Hardware multi-node scheduling and CSI recovery remain unverified.
- Recorded the user's [current native NetBox testing priority and deferred spare-parts scope](decisions.md#confirmed-with-the-user--2026-10-23). Clarified the existing [lab integration target](../AGENTS.md#lab-test-authority): chart/importer integration belongs on dragonvm's `fhs-test`; standalone plugin tests and renders did not close that gap. The trial's cleanup boundary did not prohibit authorized lab integration testing. This documentation change establishes no new runtime test result.
- Re-ran the current [read-only NetBox resource/API check](../ops/platform/netbox-resource-test.py) over SSH against the existing `fhs-test` / `fhs-platform` deployment: 62 API requests passed alongside a Django read; 186 device records, pod UID and zero restart count remained unchanged, with no OOM events and no server plugins enabled. The remote checkout lacked this newer script, so the checked local source was supplied through SSH stdin. This verifies existing native NetBox health, not the delivered umbrella chart or an importer end-to-end run.

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
