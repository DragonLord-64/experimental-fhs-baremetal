# Transfer preparation — 2026-10-26

Official source: `development2` at `58d49fe`, fetched from the official GitLab
remote. Previous cleanup source: `7704587`; experimental baseline: `b3f27c4`.
The single late commit changes four files. This pass integrates source changes
only; it adds no new functionality beyond the late official fixes.

## Late official changes

| Change | Reconciliation |
|---|---|
| Move LLDP package/service setup out of the network role to final HW Management play | Same all-host play/tasks and `hw_management` tag retained in site; network role remains scoped to networking |
| Restart networkd and resolved after network configuration | Both use the existing change notification; unchanged runs do not restart services |
| Refresh APT in DPDK prerequisites, ignoring failures | Existing experimental dependency task already refreshes APT; keep failure reporting, as explicitly agreed in cleanup |
| Refresh APT immediately after networking, ignoring failures | Not copied: distribution role owns repository/cache refresh; silent failure conflicts with the agreed policy |
| Broaden FHS-node play from `fhs_nodes` to `all` | User confirmed: target `all` for node preparation |
| Comment BIST include out of site | User confirmed: retain enabled installation-only BIST invocation |

The last two choices were resolved by the user: target all and leave BIST enabled.
The official
commented BIST fragment also leaves a dangling `tags` mapping; do not copy that
fragment literally. CIS remains in its separately reviewed Linux-policy play.

## Copy boundary

Copy the following whole source directories
into a clean checkout of official `58d49fe`, preserving deletions as well as new
files. Review the resulting diff before opening the official PR.

- `roles/`: includes portable Molecule files and intentional `manage_poetry`
  retirement. Preserve shared module/task helpers.
- `docs/src/`: use the experimental version and preserve official docs build
  files outside this subtree; do not copy the private handoff in `docs/`.
- `playbooks/`: includes site/provision callers, CIS preflight, download callers
  and the separately completed NetBox JSON/Nexus changes.
- `platform/`: separately transferable source; required for reviewed devpi/Squid
  services and existing NetBox integration. Include vendored chart dependencies
  and image recipe. Do not replace deployment-specific values/credentials.

Selectively merge inventory prerequisites, not the private inventory wholesale:

- `inventory/dev_env/hosts.yml`: Linux-policy group membership.
- `inventory/dev_env/netbox-inv.yml`: dynamic Linux-policy classification.
- `inventory/dev_env/group_vars/all.yml`: shared group identity, artifact/runtime
  settings and proxy variables; retain the destination's secrets/endpoints.
- `inventory/dev_env/group_vars/ubuntu24_cis_production.yml`: agreed enforcement
  and selected policy; firewall settings remain user-owned.
- `inventory/README.md`: public inventory usage and classification guidance.

Keep official CI/root settings unless a separate reviewed change requires them.
Never copy `.git/`, `ops/`, `wiki/`, experimental instructions, private inventory
archives, caches, test captures, `ops/emulators/` or the untracked
`docs/session-handoff-2026-10-22.md`. Additional test orchestration stays here;
ordinary role-local Molecule scenarios can transfer. Supply credentials separately.

## Focused verification

- Latest official fetch succeeded; upstream push URL remains `/dev/null`.
- Ansible syntax checks passed for stage-3 changed roles and `playbooks/site.yml`.
- Existing `stage3_contract.py` passed: effective CIS variables/classification,
  node preparation safety and targeted network-file ownership.
- `git diff --check` passed.

The first standalone contract invocation lacked `ANSIBLE_LOCAL_TEMP` and failed
on the sandbox's read-only default Ansible cache; rerun with a writable `/tmp`
cache passed. Syntax-only localhost inventory emits expected unmatched group
warnings. No host services, lab, firmware, firewall or production inventory were
changed. Existing full cleanup/runtime evidence remains in `EVIDENCE.md`; this
integration pass does not claim new network/boot/hardware validation.
