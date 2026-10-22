# Agent pipeline

Local task runner. The script controls the stages; each stage starts a fresh Codex process.

`screen + tests -> implement -> review -> configured checks -> done`

Failed review goes to a fresh implementer with the original task, screening context and review findings. Blockers, invalid results, failed checks and retry limits stop the run. Nothing is committed, pushed or deployed by the runner.

## Run

Requires Python 3.10+, Git and an authenticated Codex CLI. tmux is optional. Run from the private experimental checkout on a task branch. Only one task may own the checkout at a time. Existing edits and untracked files are preserved; use a clean checkout if you need an unambiguous task diff.

Write the task in a text file. Copy `config.example.json` and replace `checks` with the actual task's acceptance commands. Each command is an argv array, not a shell string. The example checks this controller only; it does not validate Ansible changes. Checks run with your user's permissions: use trusted commands and disposable environments.

Set `codex` to the absolute CLI path for automation, for example `"codex": "/home/dragon-lord/.local/bin/codex"` on dragonvm. Check that executable's `--version` and `login status` in the same noninteractive SSH environment used to launch the runner. An interactive shell can select a different installation: dragonvm's noninteractive `codex` selected `/usr/local/bin/codex` 0.142.5 while the updated user installation was 0.163.0. The older executable rejected the configured model; the updated executable ran it successfully. Keep the user's configured model unless a change is explicitly requested.

```bash
python3 ops/agent-pipeline/pipeline.py start --task-file /tmp/task.txt --config /tmp/pipeline.json
python3 ops/agent-pipeline/pipeline.py status TASK
python3 ops/agent-pipeline/pipeline.py logs TASK --lines 80
python3 ops/agent-pipeline/pipeline.py watch TASK
python3 ops/agent-pipeline/pipeline.py tmux TASK
```

`tmux` prints the attach command. The monitor shows status, agent PID/session ID, elapsed time and recent raw JSON events. It is a viewer, not an interactive Codex terminal. The detached controller keeps running when the monitor closes.

## Redirect

Humans and authorized supervising agents use the same commands:

```bash
python3 ops/agent-pipeline/pipeline.py pause TASK
python3 ops/agent-pipeline/pipeline.py redirect TASK 'Keep the original scope; also check upgrades'
python3 ops/agent-pipeline/pipeline.py resume TASK
python3 ops/agent-pipeline/pipeline.py cancel TASK
```

Commands are queued; check `status` for acknowledgement. Pause interrupts the active process group and preserves working files, logs and a patch. Resume starts a fresh agent at the same stage. Redirect does the same, adding the correction to the next prompt; a redirected review returns to implementation. A paused task stays paused. Cancel stops the task without deleting changes. Never run these against unrelated processes.

This version deliberately uses interrupt/checkpoint/restart. The installed CLI offers `codex queue`, but queued delivery is not treated as guaranteed live steering for `codex exec`. No terminal keystrokes are injected. An interruption can leave an external operation partially complete: inspect it before resuming.

## Files

Everything for the runner lives here. `runs/TASK/` is ignored by Git and private to the local user. It contains the original task, configuration, state, command history, prompts, raw events, structured results, patches and verification logs. `status` prints JSON for other agents. `agent_thread` is populated from Codex's `thread.started` event when available.

Treat run files as sensitive: agent output may contain environment details. Do not publish them without review. Tracked docs/tests stay in this directory; implementation changes for dispatched tasks go in their normal source paths.

## Limits

- Default: two review retries, eight total agent launches, one hour per stage/check. Pausing or redirecting consumes a new launch on resume.
- Review uses Codex's read-only sandbox. Implementers use workspace-write with approval policy `never`; unavailable permissions become blockers rather than interactive prompts. The runner never bypasses the sandbox. This is process isolation, not a hostile-code security boundary.
- Completion requires a valid review result, evidence, and successful configured checks. Review evidence is still agent judgment; configure checks that test the real requirement. Untracked files stay on disk and are listed, not included in Git patches.
- Authentication, sandbox, network or usage failures stop the task. Restart as a new task with the previous evidence; stopped runs are immutable.
- A killed controller cannot auto-recover. Status records the worker PID for diagnosis; verify it is alive. Do not resume by signalling a PID copied from old state.
- Runtime cleanup/retention and CI/GitHub issue dispatch are not implemented.

## Test

```bash
python3 -m unittest discover -s ops/agent-pipeline/tests -v
```

Tests use a fake Codex executable, with no model calls. CLI flags were checked against installed `codex exec --help` and [official noninteractive documentation](https://developers.openai.com/codex/noninteractive). See [validation](VALIDATION.md) for dragonvm results and executable selection in the real smoke test.
