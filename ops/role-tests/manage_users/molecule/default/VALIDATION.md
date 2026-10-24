# dragonvm validation

2026-10-22, isolated input `642ccc13c5e1e93479b8dc4d97d724e470f78ae4`
plus this working-tree change. The pipeline supervisor executed the container
commands through `.pipeline-bridge/`; the implementation worker did not create
containers, change host accounts/services, commit, push or deploy.

Command: `PATH=/tmp/fhs-molecule-venv/bin:$PATH bash ops/role-tests/manage_users/run.sh`.
The supervisor first installed the pinned collections from
`ops/role-tests/dependencies/requirements.yml` into `build/molecule-collections`.

Successful run: `fhs-users-1792652406-bbfeb95e`, exit 0. Artifacts:
`build/reports/molecule/fhs-users-1792652406-bbfeb95e/`.

- Fresh synthetic account absent before convergence; role created it and state
  verification passed.
- Unchanged rerun: `ok=8 changed=0 failed=0`; Molecule idempotence passed,
  followed by another state verification.
- Sudo policy changed to password-required; resulting state verification passed.
- Deliberate shell/key/sudo-mode drift was observed before repair; the actual
  role repaired it and full resulting-state verification passed.
- Isolation assertions passed: unprivileged, zero mounts, 512 MiB, one CPU,
  128 PIDs. Destroy passed; `cleanup.log` records `exit=0` and
  `remaining-containers.txt` is empty.

Toolchain: Python 3.14.4, Ansible core 2.20.1, Molecule 25.4.0,
ansible-compat 25.12.0, Docker client/server 29.8.1. `pip check` passed.
The immutable Ubuntu image digest is recorded in the runner and `versions.txt`.
APT installation succeeded but took several minutes. Deprecation warnings from
Ansible's managed-string option and authorized_key's text imports remain visible.

Baseline: `/tmp/fhs-manage-users-screen-baseline.txt` recorded the missing `users`
role, missing Molecule and all-role runner's false success with no discovered
scenarios. First implementation run `fhs-users-1792652307-951fd0bc` exited 2
before creation: Docker's lowercase missing-object diagnostic was rejected by
the destroy check. Detection was fixed; its remaining-container file was empty.
Bridge logs are `.pipeline-bridge/{toolchain,cycle-1,cycle-2,cycle-3}.log` (local ignored
artifacts). Preserve report directories externally when retaining run evidence.

No production role behavior changed. `fhs_users` remains unused, and role
argument-spec sudo default still differs from the task default; the integrated
role README documents the actual task behavior. Other scenarios
remain unchanged and unvalidated. See [instructions and limits](README.md).
Container success does not validate Bifrost guest provisioning or real hardware.

Review correction: the runner now pulls the pinned digest before image inspection,
with a 180-second timeout. `bash -n ops/role-tests/manage_users/run.sh
scripts/molecule-test-all.sh` and `git diff --check` passed. Supervisor request
`validate_image_prerequisite_cycle_3` returned 0. Its prerequisite probe rejected
image inspection until a real digest pull completed, then the full cycle passed
as `fhs-users-1792652980-488fd0af`. That run verified fresh state, an unchanged
rerun (`ok=8 changed=0 failed=0`), changed sudo policy, observed drift and repair,
and container isolation. Its report directory records cleanup `exit=0` and an
empty `remaining-containers.txt`. No shared images were removed. This checks
missing-cache prerequisite ordering; the real pull used the cached digest, so
an uncached image download was not observed.


## 2026-10-24 relocation

The same custom scenario and bounded runner moved under `ops/role-tests/`.
The runner now selects that project and resolves the role from root `roles/`.
A stub-CLI check verified project selection, role path and cleanup log; it is not
a new Docker lifecycle run. The official legacy scenario remains separately at
its original source path. The live results above retain their original scope.
