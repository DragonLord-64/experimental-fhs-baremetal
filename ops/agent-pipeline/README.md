# Agent pipeline

`task intake -> scout -> one implementation worker -> configured checks -> user review`

Small local runner, inspired by FoodReserve's [task lifecycle](https://github.com/DragonLord-64/FoodReserve-2D/blob/main/docs/project-management/task-pipeline.md) and [manager guidelines](https://github.com/DragonLord-64/FoodReserve-2D/blob/main/docs/project-management/pipeline-manager-proposal.md), inspected 2026-10-24. No screening or review agent. One task owns this checkout; work stays in its original scope. Larger feature acceptance stays separate from a small task's completion.

## Tasks

Requires Python 3.10+, Git and authenticated Codex CLI. Pin the absolute `codex` executable for automation; see [executable selection and historical validation](VALIDATION.md). The user's configured model is inherited. tmux is optional.

Write a short task: goal, allowed paths, acceptance, explicit exclusions. Copy `config.example.json`, adjust `scope` and choose the smallest useful `checks` (argv arrays, no shell). The example validates this runner only. Configure trusted checks for disposable environments.

```sh
python3 ops/agent-pipeline/pipeline.py intake --task-file /tmp/task.txt --config /tmp/pipeline.json
python3 ops/agent-pipeline/pipeline.py scout
python3 ops/agent-pipeline/manager.py dispatch-next
python3 ops/agent-pipeline/pipeline.py status TASK
python3 ops/agent-pipeline/pipeline.py logs TASK --lines 80
```

Intake records a queued task without starting a model. Scout only reads status and controller PID liveness. The manager dispatches one queued task in arrival order; running or paused work prevents dispatch. It never invents tasks or resumes paused/blocked work. PID liveness is diagnostic, not proof that the original controller still owns that PID. Reconcile stale state and actual processes before recovery. `start` remains immediate intake/dispatch. No scheduler service is installed.

The worker implements and supplies evidence. The controller owns acceptance checks, so the worker must not repeat them. Additional checks need a specific changed behavior or observed failure. Duplicate configured commands are rejected. Defaults: 600 seconds per worker, 120 per check, three total launches including resumes. Increase budgets only for the actual task. `scope` is prompt guidance, not a filesystem security boundary. Existing saved configurations retain their explicit limits; legacy `max_retries` remains accepted without a review gate.

The controller records `done` only after a valid result and successful checks; `review_required: true` means the user reviews it. The caller then publishes under the private-origin standing order. The runner does not commit, push or deploy.

## Controls

```sh
python3 ops/agent-pipeline/pipeline.py pause TASK
python3 ops/agent-pipeline/pipeline.py redirect TASK 'Keep the original goal; correct this detail'
python3 ops/agent-pipeline/pipeline.py resume TASK
python3 ops/agent-pipeline/pipeline.py cancel TASK
python3 ops/agent-pipeline/pipeline.py watch TASK
python3 ops/agent-pipeline/pipeline.py tmux TASK
```

Controls for active tasks are queued; check status for acknowledgement. Pause/redirect interrupts the owned process group, saves a patch and resumes with a fresh worker. A paused task stays paused. Cancel preserves files. Queued tasks can be cancelled before dispatch. Never control unrelated processes. An interrupted external operation needs inspection before retry. Stopped runs are immutable; retain evidence when starting a replacement. A killed controller cannot auto-recover.

`runs/TASK/` is ignored and private: task/config, prompts, raw events, results, patches and check logs. Untracked files stay on disk; patches do not include them. Inspect sensitive output before publishing. Workers use workspace-write and approval policy `never`; permission failures become blockers.

## Cluster/setup manager

```sh
python3 ops/agent-pipeline/manager.py status
python3 ops/agent-pipeline/manager.py lab-status
python3 ops/agent-pipeline/manager.py lab-up
```

Run locally. `lab-status` inspects existing nodes, pods, deployments, services and PVCs over the configured dragonvm SSH connection, always naming `fhs-test`. `lab-up` explicitly calls the existing [lab lifecycle helper](../kubernetes/README.md); it does not run acceptance tests or deploy the platform. Both host operating systems stay running. There is no periodic agent, automatic repair, cluster deletion or host lifecycle action. If SSH is unreachable follow the [wake protocol](../../AGENTS.md#dragonvm-wake-protocol), wait at least 60 seconds, then inspect preserved state. Network sandbox denial alone does not mean the VM is down.

## Checks

```sh
python3 ops/agent-pipeline/checks.py                          # changed tracked source + whitespace
python3 ops/agent-pipeline/checks.py path/to/changed.py       # explicit files, including new files
python3 ops/agent-pipeline/checks.py --all                    # full tracked syntax audit
python3 -m unittest discover -s ops/agent-pipeline/tests -v   # runner changes only
```

The audit checks Python/JSON/shell syntax and local Markdown file links, excluding code fences, images and anchors. It does not execute project code or replace Ansible lint, Helm lint, documentation builds or behavioral tests when those are relevant. The private GitHub workflow uses the same entry points and only runs controller tests for Python controller changes. Existing upstream GitLab CI remains the source-side workflow.

Tests use fake workers and temporary repositories, with no model calls or deployments. Platform/importer changes still require the [real chart/importer lab acceptance](../platform/inventory-alignment/README.md); docs and controller changes do not.
