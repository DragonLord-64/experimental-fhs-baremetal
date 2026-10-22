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
