# Align role implementation, retain consolidated documentation

Goal: bring experimental Ansible role implementation under `roles/` into line
with current official `development2`, preserving the experimental documentation
layout and content. User then wants to work through roles individually to reduce
recurring execution errors and improve repairability.

Source: official fetch-only upstream
`ska-telescope/sdi/ska-mid-cbf-fhs-baremetal`, `development2`, observed at
`7704587` on 2026-10-26. Refresh/read the branch before implementation; record the
exact source SHA and any change since this comparison. Never push upstream.

Scope: role code/defaults/templates/handlers/metadata under `roles/`; concise
alignment evidence and a role testability checklist under `ops/role-tests/`.
Preserve all documentation, including role READMEs and `docs/src/` include pages.
Do not replace complete role directories blindly. Preserve unrelated user work.

Comparison found 13 implementation files differing across seven roles:
filebeat, manage_bittware_sdk, manage_dpdk_ark_doca, manage_fhs_exporter,
manage_venvs, setup_fhs_network and setup_fpga_host. The official tree adds LLDP
setup, rsync setup and firmware reconnect checks. Experimental has Filebeat setup
and different exporter, venv and APT behavior. Match the official implementation
as requested; record experimental behavior being displaced, especially Filebeat
setup used by the platform. If removal breaks an existing supported integration,
report the concrete conflict before silently discarding it or expanding scope.
Do not improve/refactor roles during the alignment task.

Acceptance:
- Every non-documentation role file matches the recorded official source, or a
  specific unresolved compatibility conflict is explicitly reported.
- Existing role documentation and its include structure are unchanged.
- Run focused available Ansible syntax/lint checks for changed roles; inspect
  affected entrypoints and report missing dependencies rather than claiming
  runtime validation. No whole-suite/harness expansion for this sync.
- Record a concise role-by-role testability checklist: existing checks, feasible
  local/container/VM checks, hardware/production requirements and untested gaps.
  Prioritize dependency order and recovery impact: APT/pip sources, venvs,
  artifact retrieval, SDK, services/exporters and hardware roles.
- Commit and push completed validated changes only to private origin.

Follow-up workflow: review and improve ONE role at a time with the user. For each,
identify expected behavior, reproduce a concrete failure where possible, use
existing fixtures/lab, check first install plus unchanged rerun and relevant drift
repair, and make only justified focused fixes. Separate code bugs, environment
prerequisites and hardware limitations. Do not claim a simulated role passed on
physical hardware. Do not create a large new test framework or automatically
launch every role. Archived roles remain separately identified.

Safety: never shut down/reboot/suspend/hibernate/halt/power off either server,
including by invoking role handlers that do so. Hardware firmware/power/network
roles may be inspected and tested with safe substitutes only unless a suitable
explicitly authorized scope exists; the unconditional host safety rule still
applies. No production access or physical firmware operations in this task.
