# Screen baseline

2026-10-22; accepted source `c06c5587492d21f93ad0700975901be810c5e47e`.
Production tasks, defaults, template and tags remain unchanged. Only this role's
container harness changed; accepted `manage_users` files are unchanged.

## Observed runs

- Initial local probe: Docker socket permission denied. No worker Docker retry;
  no containers created by the worker. Raw probes remain in ignored
  `build/reports/molecule/setup-pip-source-screen-baseline/`.
- Supervisor operation `setup_pip_source_screen_baseline_20261022_01`: actual
  role fresh converge passed (`changed=1`), verifier failed its guessed managed
  comment bytes. This was a harness defect, not a production defect. Owned
  teardown passed, shell exit 1, remaining-container file empty.
- Supervisor operation `setup_pip_source_screen_baseline_20261022_02`: return 0;
  fresh converge `ok=4 changed=1`, unchanged rerun `ok=4 changed=0`, strict
  idempotence passed. Both verifications passed exact noncomment config bytes,
  root:root/0644 and unrelated fixture content. The verifier permits Ansible's
  comment wrapper lines; it does not derive expected configuration from the
  template. Effective privilege=false, mounts=0, 512MiB/1CPU/128PIDs assertions
  passed. Owned destroy passed; cleanup exit 0, remaining-container file empty.

Command: [README](README.md). Supervisor responses and raw lifecycle logs:
ignored `.pipeline-bridge/response.json`, `baseline-01.log`, `baseline-02.log`.
Successful run artifacts:
`build/reports/molecule/setup-pip-source-baseline/fhs-pip-1792684208-1675c7d0/`
(`test.log`, `versions.txt`, `cleanup.log`, `remaining-containers.txt`).
Supervisor-reviewed verifier SHA256:
`ffd28af9027821904ff511961cc361d5708469138cdbf18ccc6b4a4b2343fe7e`.
Executable harness sources still match the matching response's reviewed hashes;
this validation note was updated after that execution.

Local `bash -n scripts/test-setup-pip-source.sh`, six scenario YAML parses using
`/tmp/fhs-molecule-venv/bin/python`, and `git diff --check` passed.
No host Python installation, private pip contact or hardware test occurred.

## Implementation handoff

Old converge imported nonexistent `pip_index`; old container requested privilege
and a writable host cgroup mount. Neither old harness nor test-all was run.
The replacement imports actual `setup_pip_source` and mirrors
`playbooks/site.yml:53` dynamic include/apply role tags using `.invalid` fixtures.
Production validation asserts nonempty URL, then templates `/etc/pip.conf`.
No demonstrated production behavior defect exists.

Extend the same local/CI entrypoint with separate final reports: changed URL and
trusted-host must update exact state and report change; observed corruption must
be repaired with actual change then zero-change rerun; empty URL must fail and
preserve prior bytes/metadata. Check broader unrelated-file preservation,
effective network/devices/ports isolation and owned cleanup on success/failure.
Keep meaningful state assertions and concise adjacent comments on every changed
Ansible/Molecule logical block. Production fixes need demonstrated baseline
failure and the user's narrow allowed scope.

Before tag cleanup establish original selected task sets and isolated behavior;
compare whole-role playbook selection and dynamic `include_role.apply`
inheritance afterwards. Current tasks both carry `[pip_index, config]`; the site
wrapper applies `setup_pip_source` (distribution play). No distinct subfunction
is evident, but original selection comparison has not yet been executed.
Preserve special/dependency/static/dynamic inheritance semantics if encountered.
Submit each live run as a unique supervisor bridge operation with exact argv and
source hashes; worker must not invoke Docker or fabricate acceptance. Full
acceptance and independent review remain pending; no subsequent role launch.
