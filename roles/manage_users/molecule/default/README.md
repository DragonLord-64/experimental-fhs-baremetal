# manage_users container test

[Observed dragonvm run](VALIDATION.md).

Run from the repository root on dragonvm or a future Docker-capable CI runner:

```sh
python3 -m venv /tmp/fhs-molecule-venv
. /tmp/fhs-molecule-venv/bin/activate
pip install -r tests/molecule/requirements.txt
ANSIBLE_LOCAL_TEMP=/tmp/fhs-molecule-galaxy ansible-galaxy collection install \
  -r tests/molecule/requirements.yml -p build/molecule-collections
scripts/test-manage-users.sh
```

Use Python 3.14 for the isolated controller toolchain. This does not replace the
Poetry application/lint environment. Docker CLI and daemon access are required;
the script records both versions. The Ubuntu 24.04 image is digest-pinned in the
script. The runner pulls that digest before inspecting it, including on a fresh
Docker runner (three-minute pull timeout). Python is installed in the disposable
container; the role installs sudo.
APT package versions follow Ubuntu's archive, so the test is not an offline image.
`scripts/molecule-test-all.sh` invokes the same entry point; other roles' preserved
scenarios are not validated by this command.

The actual role discovers `fixtures/moleculeuser.pub` on the controller. The
username comes from its filename, not `fhs_users` (currently unused by the role).
The key and fixed password hash are synthetic fixtures. No private key, Vault,
real inventory or host account is used. `ansible_user` is container root.

The sequence checks fresh creation, a strict unchanged rerun, changing sudo from
passwordless to password-required, then recovery after changing the shell,
emptying authorized_keys and changing the sudoers mode inside the container.
It first asserts the drift exists. Verification reads passwd/shadow, group
membership, home/shell, exact key and ownership/modes, sudoers content and
`visudo`/`sudo -l` results. Shadow assertions use `no_log`.
The role adds groups and keys; removal of unmanaged entries is not its contract.

One unique run-labelled container uses at most 512 MiB, one CPU and 128 PIDs,
without privileged mode, mounts or published ports. The runner has a 15-minute
bound. Molecule destroy and the shell trap remove only that run's owned name.
After an uncatchable kill, inspect the run label before manually removing its
container; never prune shared Docker resources.

Keep `build/reports/molecule/<run>/` as a CI artifact, including failed runs:
`test.log`, `versions.txt`, `cleanup.log` and `remaining-containers.txt`.
An empty remaining-container file plus `exit=0` records successful cleanup.
No CI runner or deployment is installed by this change.

Screening evidence: the old scenario failed syntax checking with role `users`
missing; the old all-role script returned success without finding any scenarios.
Molecule was absent, and the worker lacked Docker socket access. Authorized
container execution goes through the supervisor bridge for this pipeline run.

This tests provisioning/configuration of Linux userland, not telescope
applications, kernel/boot, PXE, NIC/FPGA or physical hardware. Bifrost with
isolated disposable VMs remains a separate provisioning layer: restricted
Bifrost API smoke is verified; its full guest-provisioning cycle is unverified.
The role README is the canonical source included by Sphinx documentation.
