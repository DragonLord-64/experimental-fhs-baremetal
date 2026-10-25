# Decisions and open questions

## Confirmed with the user — 2026-10-21

- Use a private GitHub experimental repository and a separate checkout in the home directory.
- The agent may push experimental changes there; the user transfers accepted changes to official SKA repos.
- The user plans to set up a Linux VM using Hyper-V on a Windows gaming PC.
- Cloud spending must be below US$10 per month; use existing hardware first.
- Keep a short plan and a linked knowledge wiki inspired by DragonMind.
- Grafana dashboards are a workflow example; detailed dashboard scope is deferred.

## Confirmed with the user — 2026-10-23

- Focus on testing the current [native NetBox discovery/import and export playbooks](../docs/src/playbooks/development.md) with the [delivered platform chart](../platform/charts/fhs-platform/README.md) in the existing `fhs-test` lab on `dragonvm`; see [lab test authority](../AGENTS.md#lab-test-authority). The [2026-10-24 alignment validation](../ops/platform/inventory-alignment/VALIDATION.md) records subsequent integration evidence and its limits.
- Spare-parts and Inventory integration were deferred at this point; the user resumed that scope on 2026-10-24. The [separate plugin trial](../ops/platform/inventory-trial/README.md) remains evidence for its bounded asset tests.
- The [`netbox.netbox` Ansible collection](../playbooks/netbox/requirements.yml) runs on the control machine and supports native NetBox API objects. It is distinct from the trial's NetBox Inventory server extension; the aligned importer now requires that extension for physical assets.

## Confirmed with the user — 2026-10-24

- Align the tested plugin, main deployment and importers; retain physical assets by serial across installed-record removal/replacement. Chassis identity follows serial, not hostname. Complete, explicitly selected discovery scopes may reconcile absence; partial or failed scans preserve records.
- Use one public [NetBox importer](../playbooks/netbox/netbox_import.yml) for Linux/FHS and Nexus, with internal family tasks and a compatibility Nexus wrapper. Never run server discovery on a switch.
- Keep manual DAC stock/quarantine tracking available without inventing cable endpoints. Asset status/history and installed topology serve different purposes; change-log retention defaults to 90 days.

## Proposed, not implemented

- Fast lint and syntax checks, disposable Kubernetes tests, VM provisioning tests, and separate physical hardware verification.
- A test runner on the Linux VM, with identical local and CI commands.
- Captured telemetry fixtures, dashboard query checks, and screenshot artifacts for issue review.

## Open questions

- Guest boot/provisioning after the successful KVM capability check; see [provisioning limits](../ops/provisioning/README.md).
- CI provider configuration and runner access.
- Representative telemetry capture format and coverage.
- Which roles require real hardware, system VMs, or simulated device interfaces.

## Observed implementation

The Hyper-V guest, persistent platform and restricted Bifrost fixture are implemented within the limits recorded in [VM operations](../ops/kubernetes/README.md), [platform validation](../ops/platform/VALIDATION.md) and [provisioning checks](../ops/provisioning/README.md). The [controller](../ops/agent-pipeline/README.md) owns implementation/check execution; its [validation](../ops/agent-pipeline/VALIDATION.md) records executable selection and bounded real-run evidence. Fake-agent tests alone do not prove a real task completes.

## Confirmed with the user — 2026-10-24 pipeline cleanup

- Keep task intake/scouting and one implementation worker, with user review. Use a small CLI manager for queue dispatch and existing lab inspection. No review agent or per-task manager agent.
- Match checks to changed behavior; the controller runs configured acceptance once. Default worker/check budgets are ten/two minutes. Larger runtime changes still need real chart/importer lab acceptance. See [workflow and commands](../ops/agent-pipeline/README.md).
