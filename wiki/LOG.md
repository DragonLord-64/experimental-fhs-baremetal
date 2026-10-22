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
