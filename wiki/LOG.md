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

## 2026-10-22

- Corrected monitoring emulator overlay mutation and cleanup restoration; six local contract tests pass. Added bounded configuration selection and stricter live assertions. Supervisor integration request is pending; no new deployment or data-readiness claim. See [current evidence and remaining checks](../ops/emulators/VALIDATION.md).

- Diagnosed the bounded emulator integration failure: Prometheus had not reloaded its changed ConfigMap. Supervisor-run explicit reload and real bounded verification passed (13 FHS, four switches, three links). Added checked reloads and fixture checksum rollouts; eleven local tests pass. Full shared expansion awaits measured supervisor review. See [validation evidence](../ops/emulators/VALIDATION.md).

- Added bounded replay of actual native FHS exporter responses after full shared scrape availability failed. Supervisor bounded/full protocol and Prometheus assertions passed (132 FHS, 51 switches, 648 mesh links; 13,264 FHS/node and 11,073 Cisco series). Reset, exact cleanup restoration and full reapply passed; final platform check hit a failed local tunnel and fresh read-only proof is pending. Independent review remains required. See [validation and resource evidence](../ops/emulators/VALIDATION.md).

- Reduced the default emulator inventory to VCCUnit1..4 / FSPUnit1..3 while retaining original full-topology identities and the optional full reference. Source regressions pass; reduced supervisor acceptance remains pending. Added a reversible source ELK pause profile with retained claims and offline render checks. See [validation](../ops/emulators/VALIDATION.md) and [platform profile](../ops/platform/README.md).
