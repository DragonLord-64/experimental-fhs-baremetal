# 2026-10-30 account environment validation

Disposable `ubuntu:24.04` Docker container on dragonvm; no host user or production
inventory changes. Current `manage_users` role run through `community.docker` as
Ansible user `ubuntu`, with privilege escalation inside the container only.
Synthetic `fhs-sdk-fixture` packages 1.0/1.1 exercise wiring, not proprietary SDK
compatibility or physical hardware.

First complete converge: 94 tasks, 32 changed, 0 failed. Independent verification:

- Shared `/opt/venvs/fhs` owned by ubuntu:bittware, mode 0750.
- Alice, Bob, ubuntu and gitlab-runner each have home-local `.bw_venv`, owned by
  that account. Key-file accounts, connection user and explicit service account
  all receive environments.
- Installer asserts actual activation (`VIRTUAL_ENV == sys.prefix`) and exact
  `BWSDK_ROOT=/usr/share/bittware-sdk`; every environment records one invocation.
- Every environment passes `python -m pip check` and runs `bw_card_monitor`.
- Alice/ubuntu pre-existing supplementary `preserved` group retained.
- Runner UID 999, own primary group and bittware supplementary group; no sudo.

Private generated keys, SDK packages and logs remain in
`/home/dragon-lord/fhs-user-environments-20261030`, outside Git. Bootstrap package
list disabled for fixture (`fhs_venv_packages: []`); production defaults remain.

Second complete converge with final ownership repair: 97 tasks, 4 ownership
normalization changes, 0 failed. All five installers skipped and counters stayed
at one. A deliberately root-owned Alice environment file returned to Alice's
ownership. The four changes reflect the newly added normalization task across
personal environments, not SDK reinstallations.

SDK upgrade 1.0 → 1.1 through the same role's SDK/environment tasks: 91 tasks,
13 changed, 0 failed. All five installer counters advanced exactly once to two;
all version markers read `fhs-sdk-fixture=1.1 /usr/share/bittware-sdk`. Independent
ownership, permissions, pip consistency, executable and account-isolation checks
passed again. No additional post-upgrade full account converge was needed.

The owned disposable container was removed after successful verification; private
controller fixture files/logs retained. This validates role wiring and version
refresh behavior only. It does not prove proprietary SDK dependencies, FPGA
hardware or production user data migrations.
