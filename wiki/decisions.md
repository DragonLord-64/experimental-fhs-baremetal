# Decisions and open questions

## Confirmed with the user — 2026-10-21

- Use a private GitHub experimental repository and a separate checkout in the home directory.
- The agent may push experimental changes there; the user transfers accepted changes to official SKA repos.
- The user plans to set up a Linux VM using Hyper-V on a Windows gaming PC.
- Cloud spending must be below US$10 per month; use existing hardware first.
- Keep a short plan and a linked knowledge wiki inspired by DragonMind.
- Grafana dashboards are a workflow example; detailed dashboard scope is deferred.

## Confirmed with the user — 2026-10-23

- Focus on testing the current [native NetBox discovery/import and export playbooks](../docs/src/playbooks/development.md) with the [delivered platform chart](../platform/charts/fhs-platform/README.md) in the existing `fhs-test` lab on `dragonvm`; see [lab test authority](../AGENTS.md#lab-test-authority). Full chart/importer integration remains to be verified.
- Defer spare-parts work and NetBox Inventory server-plugin integration until the user resumes that scope. The [separate plugin trial](../ops/platform/inventory-trial/README.md) is evidence for its bounded asset tests, not chart/importer integration.
- The [`netbox.netbox` Ansible collection](../playbooks/netbox/requirements.yml) runs on the control machine and supports native NetBox API objects. It is distinct from the trial's NetBox Inventory server extension; current playbooks do not require that extension.

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

The Hyper-V guest, persistent platform and restricted Bifrost fixture are implemented within the limits recorded in [VM operations](../ops/kubernetes/README.md), [platform validation](../ops/platform/VALIDATION.md) and [provisioning checks](../ops/provisioning/README.md). The [controller](../ops/agent-pipeline/README.md) owns fresh stage transitions; its [validation](../ops/agent-pipeline/VALIDATION.md) records executable selection and bounded real-run evidence. Fake-agent tests alone do not prove a real task completes.
