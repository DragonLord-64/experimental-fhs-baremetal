# Coherent NetBox-selected gRPC installation

Goal: make `manage_fhs_grpc` a predictable, understandable installation of ONE
controller selected by NetBox device tags, with deliberate package-index and
dependency overrides. User explicitly requests this task; do not launch it yet.
This is separate from the still-uncreated broader role-testing draft.

Read latest official development2 before implementation and coordinate with the
queued role-alignment task. Reviewed official baseline: 7704587. Preserve unrelated
work and consolidated role documentation; update affected docs for final behavior.

Sources: official playbooks/development/update_repositories.yml identifies:
- https://gitlab.com/ska-telescope/ska-mid-cbf/host-software/ska-mid-cbf-fhs-fsp-grpc-controller
- https://gitlab.com/ska-telescope/ska-mid-cbf/host-software/ska-mid-cbf-fhs-vcc-grpc-controller
Inspect selected release pyproject.toml, lock files, entrypoints, README and archive
layout, not just a moving default branch. Initial web search found the FSP GitHub
mirror, but direct GitLab main/pyproject fetches failed; upstream dependency review
is NOT completed. Resolve actual branch/release and record source revisions. No
proprietary SDK supplied; do not claim real SDK or FPGA validation.

Scope: roles/manage_fhs_grpc/, roles/manage_poetry/, playbooks/site.yml,
necessary NetBox inventory tag mapping, focused existing Molecule/role checks and
concise docs. Do not expand into proxy implementation or broad role cleanup.

Required behavior:
- NetBox device tags grpc-fsp/grpc-vcc select exactly one installation/service.
  Neither tag skips; both fail clearly before mutations. Resolve actual plugin
  tag shape. Validate before changing a previously configured host. A tag change
  stops/disables the previous owned service without deleting unrelated data.
- Move Poetry setup into gRPC, remove its standalone site invocation, and retire
  manage_poetry only after inspecting callers. Configurable venv and tested Poetry
  version; prerequisites and intended ownership explicit.
- Preserve the user's alternate pip index and necessary dependency differences.
  Compare existing full pyproject templates against upstream release metadata;
  document each necessary override and use the smallest supported adjustment.
  Do not blindly replace upstream packaging or remove required local changes.
- Use deterministic dependency resolution: preserve approved release locks where
  compatible; explicit changed index/dependency inputs produce a corresponding
  reviewed lock, not unconstrained lock regeneration on every run. Distinguish
  pip index configuration from Poetry package-source configuration. No silent
  public-index fallback or certificate-verification bypass.
- Define controller-specific card/device/region/port/bitstream settings; validate
  required inputs and real archive layouts, including suspicious FSP agilex-vcc
  paths. No guessed hardware identity or hard-coded server-specific defaults.
- Correct PATH versus PYTHONPATH. Choose explicit runtime environment and user;
  evaluate necessary FPGA/BittWare access before removing privileges. Review
  root execution of shared writable code, secrets and logs. No firewall changes.
- Honest change reporting; unchanged rerun avoids dependency re-resolution and
  service restart. Restart on relevant changes, recover a stopped owned service,
  and use an appropriate bounded systemd restart policy. Validate service config.

Acceptance: focused Molecule/container tests with tiny stand-in FSP/VCC packages
cover selection/no-selection/conflict, Poetry/index/dependency wiring, initial
install, unchanged rerun, relevant config update, tag switch and service recovery.
Use systemd-capable disposable environment for actual service checks. Reuse
existing fixtures/lab; no production access or new cluster. Add safe emulation
with real upstream software only if available and useful within scope. Report
stand-in versus actual controller results separately. Never program FPGA hardware
or reboot/shut down hosts. No unrelated full-suite/harness expansion.

Before implementation select finite exact existing acceptance commands and record
them. User reviews; after completed appropriate checks commit/push private origin
only. Do not push official repositories. No independent review agent needed.
