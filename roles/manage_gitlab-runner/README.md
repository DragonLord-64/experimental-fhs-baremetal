# Manage Gitlab Runner

The site provisioning workflow now uses `manage_users`
for accounts, system SDK and all BittWare environments. This standalone role
remains for existing direct callers; use `--tags manage_users` with `site.yml`.

Required setup for gitlab runners use by MDA development team
Example: https://git-collab.nrc-cnrc.gc.ca/haa/fsa/fpga/libraries/bittware_testing_notebooks

Creates a user called `gitlab-runner`. Create a python venv for that user called `.bw_venv`. Installs the bittware sdk using `bw_pip install`.

## Requirements
Requires the BittWare SDK for AI-860m to be installed. See `roles/manage_bittware_sdk/README.md` role.

## Tags/Usage


Select `--tags manage_gitlab-runner` in `playbooks/site.yml`. This role does not
install/register a GitLab runner daemon. It keeps the account, venv and per-user
SDK installer together. Shared `fhs_bittware_group` / `fhs_bittware_group_gid`
default to `bittware` / `666`; supplementary memberships are appended. A fresh
process must see the new group. The venv entrypoint `bw_card_monitor` plus
`python -m pip check` replaces the Python-version-specific pydantic sentinel.
An absent entrypoint or broken dependencies reruns the installer as the runner.
The installer runs with its venv activated and `BWSDK_ROOT` set. Real SDK and
FPGA behavior require separate validation; the local stand-in proves wiring only.
