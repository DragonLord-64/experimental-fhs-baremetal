# Validation

Tested 2026-10-21 on the development server and `dragonvm` (`dragon-lord-Virtual-Machine`).

| Check | Result |
|---|---|
| Local fake-agent integration suite | 11 passed; latest rerun 8.594 seconds |
| Local tmux monitor | Session opened, live status captured, session removed |
| dragonvm integration suite | 11 passed in 7.759 seconds |
| dragonvm tmux and controls | Live status captured; pause, redirect, fresh resume, logs and cancel acknowledged |
| dragonvm real Codex task | Completed screen, implementation and independent review; exact file check and 11 controller tests passed |

Remote dependencies: Python 3.14.4, Git 2.53.0 and tmux. Noninteractive SSH selected `/usr/local/bin/codex` 0.142.5; the updated user installation is `/home/dragon-lord/.local/bin/codex` 0.163.0. Both report a ChatGPT login.

Earlier real attempts stopped at screening with status `blocked`: the old executable rejected configured model `gpt-6.1-sol` and its config-isolated default `gpt-5.5`. This was an executable selection problem. Noninteractive SSH PATH excludes `~/.local/bin`; `.bashrc` returns before its PATH additions and `.profile` adds the user bin directory only for login shells. The updated executable completed an authenticated inference with the unchanged configured model `gpt-6.1-sol`, returning `CODEX_DRAGONVM_OK`.

The bounded real pipeline then used the explicit updated executable in an isolated temporary Git checkout: three maximum launches, no review retries and a 180-second stage limit. Run `real-updated-codex` reached `done` after three fresh workers. Independent review passed without findings. Controller checks verified exact `smoke.txt` bytes (`dragonvm real pipeline ok\n`) and all 11 controller tests passed in 7.736 seconds. No other tracked task changes were produced; two untracked supervisor fixtures were also present. Optional Todoist/tldraw MCP authentication errors did not block inference or completion.

Real-run evidence: `/tmp/fhs-real-e2e.3w6dfp/ops/agent-pipeline/runs/real-updated-codex`. Earlier blocked-run evidence: `/tmp/fhs-agent-pipeline-test.dyLkY1/ops/agent-pipeline/runs/{real-smoke,real-isolated-smoke}`. Raw logs are private and untracked; temporary paths are not durable archives. No existing checkout, services or Codex configuration were changed. Temporary fake-agent workspaces and monitor sessions were removed.

Pin the absolute `codex` executable in automation as described in the [README](README.md). This smoke proves a small authenticated pipeline task on dragonvm; it does not validate Ansible roles or physical hardware.


## 2026-10-24 — user review policy

The user replaced independent agent review with one implementation pass and their
own review. Twelve local fake-executable controller tests pass: one launch on the
happy path, checks remain mandatory, legacy review checkpoints resume
implementation, and pause/redirect/cancel/timeout/locking behavior is retained.
This is controller behavior evidence, not a new authenticated model smoke run.
Existing paused/blocked runs were not resumed.

## 2026-10-24 — intake, scout and manager

- Eighteen fake-worker/manager tests pass in 10.077 seconds. They cover queued
  intake, FIFO single dispatch, preserved paused/blocked work, pre-dispatch cancel,
  duplicate-check rejection, separate check timeout and existing controls/locks.
- Full tracked audit: 254 source/link file checks passed; 253 relative Markdown
  links were also inspected independently with no missing targets. New helper
  sources passed explicit syntax checks. Whitespace and workflow YAML pass.
- YAML structural inspection parsed 238 ordinary files; twelve Helm templates
  require rendering rather than a raw YAML parser. Both delivered charts pass
  Helm lint, retaining existing Grafana probe-coalescing and chart icon warnings.
  Seven source-boundary tests pass in 0.818 seconds, including chart rendering and
  preserved-source hashes. No source hash exceptions were changed.
- New manager `lab-status` completed against existing dragonvm `fhs-test`:
  node Ready, active application pods Running, retained claims Bound. Some
  deployments were already scaled to zero; no scale or restart was performed.
  No pipeline processes were found in the initial remote process inspection;
  that checkout had no `ops/agent-pipeline/runs` directory.
- No authenticated model task, deployment, hardware test, cluster lifecycle test
  or `lab-up` mutation was run. Sphinx and ansible-lint are absent locally; a full
  documentation build and full Ansible lint were not run. GitHub workflow execution
  remains pending CI. Prior wiki/emulator edits were kept outside this commit.

The full audit initially exposed invalid empty subshells in two disabled hardware
power-test blocks. Commenting their delimiters fixes parsing without activating
those blocks. Bifrost Quickstart and relocated lab Inventory-image links were
also corrected. The manager is an explicit CLI helper, not an installed watchdog.
