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

- 2026-10-22: Added the scoped [NetBox lab bootstrap and consumer path](netbox-lab.md). Private archive inspected structurally without printing values; canonical logical identities retained. Eleven offline contracts and two existing provisioning isolation checks pass. Initial supervisor API/UI readiness probe passed; persistent seed and actual Ansible/Bifrost integration remain pending.

- 2026-10-22 continuation: Prior supervisor evidence confirms 186 synthetic NetBox devices and an unchanged seed rerun with zero creations. Actual plugin invocation now succeeds but field validation remains failed; fixed sanitized diagnostics and connection-failure stale export invalidation. Twenty offline contracts pass. Further live integration and independent review remain pending; see [NetBox lab](netbox-lab.md).

- 2026-10-22: Reproduced the installed ansible-core inventory encoder’s unsafe string marker using synthetic input. Added exact marker decoding for validation and an actual-encoder regression test; 21 offline contracts pass. Supervised actual-plugin retry remains pending.

- 2026-10-22: Supervised inventory retry v9 passed authenticated readiness and plugin invocation, then failed a native-fact API GET. Added numeric HTTP-status diagnostics with a privacy regression test; 22 offline contracts pass. Read-only retry v10 queued; no further live fact mutations, target access or enrollment performed.

- 2026-10-22: Replaced per-device native interface reads with one scoped paginated query, preserving exact comparisons. All 23 lab contracts and two provisioning isolation tests pass; Compose validation passes. Added a read-only serving/resource probe and requested supervised measurements and one actual-plugin retry after the saved NetBox OOM event. No reseed or serving/resource changes made; live acceptance remains pending.

- 2026-10-22: Inspected actual pinned NetBox plugin batching and reduced its related-object URI budget to 512. Added exact assigned-interface IP comparisons and regressions for missing/stale/moved assignments; 25 lab tests and two provisioning isolation tests pass. Requested a supervised read-only retry after capacity review; live consumer acceptance remains pending. See [NetBox lab](netbox-lab.md).

- 2026-10-22: Supervisor returned matching v12 capacity hold on live consumer load and test containers. Preserved persistent inventory and candidate; actual plugin acceptance, reachable target, source-of-truth exercise and Bifrost loader/API checks remain blocked pending release.

- 2026-10-22: Reduced-population source now has stable full-order BMC/OOB offsets and an offline exact prune plan/apply library with ownership, dependency, stale-state and resume checks. Thirty lab tests and two provisioning isolation tests pass. Added [prune usage and holds](../ops/netbox-lab/README.md); bridge requests frozen reduced topology and exact supervisor dependency evidence only. No live deletion, plugin run, worker change or Bifrost operation performed. Independent review and exact parent-approved deletion plan remain pending; source acceptance is blocked on frozen evidence.
