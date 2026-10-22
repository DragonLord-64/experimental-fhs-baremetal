# Experimental test environment plan

Status (2026-10-21): the agent pipeline has passed a bounded real three-worker run on dragonvm. The dedicated Kubernetes cluster and corrected live smoke checks passed; the corrected run exited successfully; both smoke namespaces and their PVs are gone. Monitoring, provisioning and hardware test workflows remain proposed.

## Purpose and source

Use this private repository to develop and test changes to SKA Mid CBF FHS bare-metal tooling. Push experimental changes here so they can be pulled onto a test machine. The user reviews and transfers accepted changes to the official repository; the agent must not push there.

Initial files come from `ska-mid-cbf-fhs-baremetal`, branch `development`, commit `656983382383e869d3b1ff8484f14cfe05e7b832`.
GitHub rejected the original history because it contains files over 100 MB. This repository therefore starts with a snapshot of the tracked source tree. Full source history remains in the original local repository and `/home/dragonlord/experimental-fhs-baremetal-source-history.git`. Subsequent experimental commits can be transferred as patches or cherry-picked after review; the repositories do not share the initial commit ancestry.

## Compute and budget

- Use this Linux server for development and lightweight checks. At inspection it had four CPU cores, 16 GB RAM, about 3.2 GB available RAM, full swap, and 315 GB free disk.
- Confirmed `dragonvm` is the Hyper-V Linux guest: Ubuntu 26.04, eight CPUs, 11 GiB RAM (about 7 GiB available) and 67 GB free disk at inspection. Docker and minikube are installed. Nested virtualization for provisioning target VMs remains unverified.
- Target no cloud spend initially; monthly cloud spending must remain below US$10. No cloud resources have been authorized or purchased.
- Never shut down, reboot, suspend, hibernate, halt, or power off this server.

## Test layers

Replicate the user's environment as closely as practical on dragonvm and run integration tests there, with local orchestration. Assess the latest development configuration and NetBox values before deploying the stack. No full-stack deployment has been performed.

The original checkout `/home/dragonlord/ska-mid-cbf-fhs-baremetal` was fast-forwarded to official development `87dc794`. It contains the monitoring-to-platform rename, current NetBox values and tracked `bifrost-infra` source missing from the experimental snapshot. Assess and adapt that source before importing: Bifrost currently assumes privileged containers, host networking, real inventory and DHCP. The exact NetBox chart version is unconfirmed; the image tag is blank in values and requires chart default/version resolution. Resolve versions before close replication.

1. Fast checks: Ansible linting and syntax, Helm rendering, and focused custom-module tests.
2. Kubernetes integration: dedicated minikube `fhs-test` profile on dragonvm, Docker driver and containerd, four CPUs and 4096 MiB RAM. Kubernetes `v1.37.1` is running with a Ready node; the existing `monitoring` profile and default context are preserved. [Bootstrap and smoke checks](../ops/kubernetes/README.md) are implemented; live node/system readiness, DNS, Service traffic and PVC write/read checks passed. The corrected run exited successfully; both smoke namespaces and their PVs are gone. Monitoring deployment and metrics/log flow remain deferred.
3. Provisioning: disposable target VMs and isolated provisioning networks for Bifrost and system configuration roles. Check nested virtualization support before implementing this on Hyper-V. Use simulated management interfaces where appropriate.
4. Hardware: separate lab validation for FPGA cards, NIC behavior, and Cisco switches. Simulations do not establish physical hardware correctness.

Use the same test commands locally and in CI. Record the tested commit and retain logs, reports, and screenshots. The [agent pipeline](../ops/agent-pipeline/README.md) is implemented and has completed a bounded real run on dragonvm; see its [validation evidence](../ops/agent-pipeline/VALIDATION.md). A dedicated CI runner remains proposed.

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
