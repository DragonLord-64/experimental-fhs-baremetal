# Experimental test environment plan

Status: planning; infrastructure and test workflows below are proposed, not yet implemented.

## Purpose and source

Use this private repository to develop and test changes to SKA Mid CBF FHS bare-metal tooling. Push experimental changes here so they can be pulled onto a test machine. The user reviews and transfers accepted changes to the official repository; the agent must not push there.

Initial files come from `ska-mid-cbf-fhs-baremetal`, branch `development`, commit `656983382383e869d3b1ff8484f14cfe05e7b832`.
GitHub rejected the original history because it contains files over 100 MB. This repository therefore starts with a snapshot of the tracked source tree. Full source history remains in the original local repository and `/home/dragonlord/experimental-fhs-baremetal-source-history.git`. Subsequent experimental commits can be transferred as patches or cherry-picked after review; the repositories do not share the initial commit ancestry.

## Compute and budget

- Use this Linux server for development and lightweight checks. At inspection it had four CPU cores, 16 GB RAM, about 3.2 GB available RAM, full swap, and 315 GB free disk.
- The user plans to provide a Linux VM on a Windows gaming PC using Hyper-V. Confirm available resources before choosing VM sizing.
- Target no cloud spend initially; monthly cloud spending must remain below US$10. No cloud resources have been authorized or purchased.
- Never shut down, reboot, suspend, hibernate, halt, or power off this server.

## Test layers

1. Fast checks: Ansible linting and syntax, Helm rendering, and focused custom-module tests.
2. Kubernetes integration: disposable clusters on the Linux test VM; kind is the initial candidate. Exercise monitoring deployment and verify metrics and logs flow.
3. Provisioning: disposable target VMs and isolated provisioning networks for Bifrost and system configuration roles. Check nested virtualization support before implementing this on Hyper-V. Use simulated management interfaces where appropriate.
4. Hardware: separate lab validation for FPGA cards, NIC behavior, and Cisco switches. Simulations do not establish physical hardware correctness.

Use the same test commands locally and in CI. Record the tested commit and retain logs, reports, and screenshots. A dedicated runner on the test VM is proposed; pipeline implementation is still to be decided.

## Workflow example: Grafana dashboards

Dashboard requirements are deferred. This records the proposed workflow only.

1. The user describes scope and acceptance criteria in a GitHub issue.
2. The agent implements the issue on an experimental branch.
3. Tests provision Grafana and its data sources using representative telemetry.
4. Validate queries, units, labels, missing data, and counter resets; capture browser screenshots.
5. Deliver commits, test results, screenshots, and any unverified behavior for user review.
6. Validate against live lab telemetry before accepting changes into the official project.

### Telemetry evidence

Start by inspecting `monitoring/example_output`, which contains node, FHS, and switch samples. Coverage and suitability have not yet been verified.

Collect raw exporter output and a short Prometheus time series from representative servers and switches. Include device model, exporter version, units, and expected behavior. A single snapshot cannot validate rate calculations or historical panels. Sanitize identifying values consistently while preserving label relationships. Do not commit credentials.

Use those captures as repeatable fixtures, with additional cases for outages, missing metrics, and counter resets. Keep fixture provenance and distinguish captured data from synthetic cases.

## Next decisions

- Confirm Linux guest OS, VM resources, and nested virtualization support.
- Choose the runner and pipeline configuration.
- Map roles to container, VM, simulated-device, or physical-lab tests.
- Prove one monitoring deployment and one Ansible role end to end.
