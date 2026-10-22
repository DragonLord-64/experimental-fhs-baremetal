# Conversation handoff — 2026-10-21

## Goal and working repository

Build an isolated environment for developing, testing and reviewing SKA Mid CBF FHS bare-metal changes. The user pulls tested changes onto the appropriate machine and transfers accepted commits to the official project.

- Working checkout: `/home/dragonlord/experimental-fhs-baremetal`.
- Private remote: `https://github.com/DragonLord-64/experimental-fhs-baremetal`, branch `development`.
- Original checkout: `/home/dragonlord/ska-mid-cbf-fhs-baremetal`; left untouched.
- Never push to official SKA repositories. Experimental upstream push URL is `/dev/null`.
- Never shut down, reboot, suspend, hibernate, halt or power off this server.

GitHub rejected the original history because three historical binaries exceed 100 MB. The private repo starts with the current tracked files from source commit `656983382383e869d3b1ff8484f14cfe05e7b832`, rather than shared commit ancestry. Original history remains in the original checkout and `/home/dragonlord/experimental-fhs-baremetal-source-history.git`. Transfer later experimental commits by reviewed patches or cherry-picks; do not merge unrelated histories casually.

## Built and pushed

- [Test environment plan](../docs/test-environment-plan.md).
- Root [agent instructions](../AGENTS.md) and [task workflow](../ops/AGENTS.md).
- [Linked wiki](INDEX.md), [decisions](decisions.md), [resource layout](resource-layout.md) and [documentation backlog](TODO.md).
- [Agent controller](../ops/agent-pipeline/README.md), with all system code, tests, configuration and validation under `ops/agent-pipeline/`.

Latest implementation commits at handoff: `97f264b` (controller) and `9fc11b0` (dragonvm validation). This handoff is a subsequent documentation change.

## Agent execution design

Final decision: a script owns transitions; no manager agent is needed for automated runs. Four stages, three workers:

1. Screen the task and relevant repository information.
2. The same worker establishes tests and baseline evidence.
3. A fresh worker implements from the original task, filtered handoff and tests.
4. A fresh reviewer checks the original intent, semantics, scope and correctness, beyond passing assertions.

Failed review returns to a fresh implementer with updated findings. Retries and launch counts are bounded. Blockers stop with evidence. Fresh context must retain original requirements and constraints.

The controller implements status, logs, watch, tmux, pause, resume, redirect and cancel. Humans and authorized agents use the same interface. tmux is a live viewer, not an interactive Codex terminal. Redirect uses interruption, checkpoint and a fresh process; live queue delivery was not established for `codex exec`. Runtime evidence is ignored under `ops/agent-pipeline/runs/`.

```bash
python3 ops/agent-pipeline/pipeline.py start --task-file /tmp/task.txt --config /tmp/pipeline.json
python3 ops/agent-pipeline/pipeline.py status TASK
python3 ops/agent-pipeline/pipeline.py tmux TASK
python3 ops/agent-pipeline/pipeline.py redirect TASK 'Updated instruction'
python3 -m unittest discover -s ops/agent-pipeline/tests -v
```

Read the controller README before use. Configure checks for the actual task; example checks validate only the controller. The controller does not itself commit, push or deploy.

## Validation and current blocker

See [VALIDATION.md](../ops/agent-pipeline/VALIDATION.md).

- Local and dragonvm fake-agent integration suites: 11 tests passed each.
- Actual tmux monitoring verified locally and remotely.
- On dragonvm, pause, redirect, fresh resume, logs and cancel were acknowledged.
- Real authenticated Codex execution remains unverified. Remote configured model `gpt-6.1-sol` and config-isolated CLI default `gpt-5.5` were both rejected by the remote ChatGPT login before task execution. The controller correctly reported `blocked`.
- Remote hostname: `dragon-lord-Virtual-Machine`; Codex CLI 0.142.5, Python 3.14.4, Git 2.53.0, tmux installed.
- SSH access worked using `ssh -F ~/.ssh/config dragonvm`; the builder reported an ownership/permission problem with system SSH configuration when not selecting the user config explicitly.
- Temporary remote evidence: `/tmp/fhs-agent-pipeline-test.dyLkY1/ops/agent-pipeline/runs/{real-smoke,real-isolated-smoke}`. Preserve needed evidence before temporary cleanup.

Next immediate step: resolve remote account/CLI model compatibility, then repeat a bounded real end-to-end smoke in an isolated checkout. Do not treat fake-agent tests as proof that a real coding task completes. Do not silently change the user's model preferences.

## Test infrastructure direction

The development server has four CPU cores and 16 GB RAM. Inspection found about 3.2 GB RAM available, swap full, and 315 GB free disk. Use it primarily for editing and lightweight checks.

The user plans a Linux VM on a Windows gaming PC using Hyper-V. VM resources and nested virtualization remain to be confirmed. Do not assume dragonvm is that planned VM without checking. Aim for zero cloud spend; the user's ceiling is below US$10/month. No cloud purchase authorized.

Planned layers: lint/syntax and focused module tests; disposable Kubernetes monitoring tests (kind proposed); Molecule containers for suitable roles; VMs for networking/kernel/boot behavior; isolated Bifrost provisioning networks; separate physical FPGA/NIC/Cisco verification. These test environments have not been implemented by this conversation.

## Role review findings

Static inspection only; role runtimes and upgrades have not been measured or executed.

- Existing GitLab CI runs lint/docs, without role-test execution in the inspected root configuration.
- Molecule scenarios exist, but the runner references an absent collection path; Molecule is not declared in project dependencies. Some converge imports are stale (`venvs` versus `manage_venvs`).
- DPDK removes its existing build/source tree and rebuilds every run.
- FHS exporter forces pip reinstallation and removes its installer archive each run.
- gRPC regenerates Poetry locks/installs with change reporting suppressed, while service templates force changes/restarts.
- BIST repeats dependency compilation/installation; offline BIST uses clean builds and ignores compilation failures.
- Runner environment uses a Python 3.12 pydantic directory as an existence marker, which does not establish installed SDK/dependency versions.
- Venv creation is guarded only by an existing Python executable, so interpreter changes need explicit handling.
- Bittware SDK already compares installed/requested package versions; retain useful existing logic.

Proposed test matrix: fresh install, unchanged rerun, A-to-B upgrade, recovery/drift. Measure timings and actual effects, not just Ansible changed counts. Start with users to establish the harness, then exporter, BIST and DPDK. No role fixes have been made yet.

Reuse candidates: Prometheus community collection for Prometheus/Node Exporter; built-in pip for generic Python installation; Kubernetes Helm module for release operations. Evaluate offline resources and upgrade behavior first. Keep SKA-specific orchestration. Kubespray is an architectural option, not an agreed migration.

## Resources and NetBox

Keep the controller resource drive for packages and dependencies. Proposed separate packages, protected secrets, sanitized telemetry and test fixtures directories; configurable root, Git-tracked versions/checksums, early prerequisite validation, independent backups. Vault unlock credentials stay separate.

Keep reusable defaults and standard profiles in Git. Keep genuinely global settings in a small `group_vars/all.yml`; avoid moving every variable there. NetBox owns device/site facts and selected overrides; secrets stay protected elsewhere.

The large Ubuntu CIS policy stays in Git at `inventory/dev_env/group_vars/ubuntu24_cis_production.yml`. A documented tag-to-group example lets NetBox select policy membership. It is a proposal, not a live inventory change. Verify actual plugin tag shape and resolved precedence before use; config context values do not automatically override every Ansible variable source. The existing NetBox inventory enables config contexts.

## Grafana workflow example

Detailed dashboard requirements are deferred. Proposed flow: GitHub issue and acceptance criteria -> implementation -> reproducible telemetry-backed tests -> query/unit/label/missing-data/counter-reset checks -> browser screenshots and test evidence -> live lab validation.

Inspect existing `monitoring/example_output` first. Capture raw exporter output plus short Prometheus time series from representative servers/switches, with device/exporter versions, units and expected behavior. Sanitize consistently and preserve provenance. A static snapshot alone cannot establish rate/history correctness. This workflow is not yet implemented.

## Documentation requirements

Match the user's existing writing voice: super brief, practical, actual tags and normal commands; read nearby docs first. Exactly one README inside each role folder, included/referenced from Sphinx/Read the Docs. Do not maintain duplicate role prose.

The user likes the current overall docs structure and diagrams. At least the FHS configuration PNG was opened and readable. Preserve useful structure while reconciling drift.

Backlog covers NetBox and imports, monitoring architecture/deployment, Grafana setup, development playbooks now used operationally, switch POAP under `playbooks/development/switch-poap/`, and checking commands, diagrams, links and docs builds. These are recorded tasks, not completed documentation migrations.
