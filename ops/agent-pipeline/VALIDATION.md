# Validation

Tested 2026-10-21 on the development server and `dragonvm` (`dragon-lord-Virtual-Machine`).

| Check | Result |
|---|---|
| Local fake-agent integration suite | 11 passed; independent review accepted |
| Local tmux monitor | Session opened, live status captured, session removed |
| dragonvm integration suite | 11 passed in 7.759 seconds |
| dragonvm tmux and controls | Live status captured; pause, redirect, fresh resume, logs and cancel acknowledged |
| dragonvm real Codex task | Blocked by account/model compatibility before task execution |

Remote dependencies: Python 3.14.4, Git 2.53.0, Codex CLI 0.142.5 and tmux. Codex reports a ChatGPT login.

The real smoke used an isolated temporary Git checkout, a task creating only `smoke.txt`, three maximum launches, no review retries and a 120-second stage limit. The configured model `gpt-6.1-sol` was rejected as unsupported for that account. A retry using `--ignore-user-config` selected the CLI default `gpt-5.5`, which was also rejected. Both runs stopped at screening with status `blocked`; no completion was claimed.

Remote evidence remains in `/tmp/fhs-agent-pipeline-test.dyLkY1/ops/agent-pipeline/runs/` under `real-smoke` and `real-isolated-smoke`. This is temporary storage. No existing checkout, services or Codex configuration were changed. Temporary fake-agent workspaces and monitor sessions were removed.

Next: select a model supported by dragonvm's account/CLI and repeat the real smoke. Fake tests verify the controller; they do not establish that an authenticated coding task can complete there.
