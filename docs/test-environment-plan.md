# Experimental test environment plan

Status (2026-10-21): the agent pipeline completed a bounded real three-worker run on dragonvm. The persistent platform passed NetBox retention and selected monitoring checks; the restricted Bifrost API and KVM creation checks passed. Guest provisioning, full emulation scale and physical validation remain unproved. See [platform results](../ops/platform/VALIDATION.md) and [provisioning limits](../ops/provisioning/README.md).

## Purpose and source

Use this private repository to develop and test changes to SKA Mid CBF FHS bare-metal tooling. Push experimental changes here so they can be pulled onto a test machine. The user reviews and transfers accepted changes to the official repository; the agent must not push there.

Initial files come from `ska-mid-cbf-fhs-baremetal`, branch `development`, commit `656983382383e869d3b1ff8484f14cfe05e7b832`.
GitHub rejected the original history because it contains files over 100 MB. This repository therefore starts with a snapshot of the tracked source tree. Full source history remains in the original local repository and `/home/dragonlord/experimental-fhs-baremetal-source-history.git`. Subsequent experimental commits can be transferred as patches or cherry-picked after review; the repositories do not share the initial commit ancestry.

## Compute and budget

- Use this Linux server for development and lightweight checks. At inspection it had four CPU cores, 16 GB RAM, about 3.2 GB available RAM, full swap, and 315 GB free disk.
- Confirmed `dragonvm` is the Hyper-V Linux guest: Ubuntu 26.04, eight CPUs, 11 GiB RAM (about 7 GiB available) and 67 GB free disk at inspection. Docker and minikube are installed. Nested KVM VM/vCPU creation passed; guest boot remains untested.
- Target no cloud spend initially; monthly cloud spending must remain below US$10. No cloud resources have been authorized or purchased.
- Never shut down, reboot, suspend, hibernate, halt, or power off this server.

## Test layers

Keep a persistent test lab on dragonvm, replicate the user's environment as closely as practical, and run integration tests against that environment with local orchestration. Use [lifecycle commands](../ops/kubernetes/README.md) to stop/resume the cluster without deleting it. VM-local storage needs external backups; no delete/reset helper is provided. Imported source provenance, chart selection and VM overrides are documented in [ops/platform](../ops/platform/README.md). Source Bifrost assumes privileged containers, host networking, real inventory and DHCP; the restricted API fixture does not replicate that deployment.

1. Fast checks: Ansible linting and syntax, Helm rendering, and focused custom-module tests.
2. Kubernetes integration: dedicated minikube `fhs-test` profile on dragonvm, Docker driver and containerd, four CPUs and 6144 MiB RAM. Kubernetes `v1.37.1` is running with a Ready node; the existing `monitoring` profile and default context are preserved. [Bootstrap and smoke checks](../ops/kubernetes/README.md) are implemented; live node/system readiness, DNS, Service traffic and PVC write/read checks passed. The corrected run exited successfully; both smoke namespaces and their PVs are gone. Selected synthetic metrics and authenticated APIs passed. The [bounded Filebeat fixture](../ops/platform/logging/validation.md) later passed using filestream; physical telemetry and the journald role remain unverified.
3. Provisioning: disposable target VMs and isolated provisioning networks for Bifrost and system configuration roles. KVM creation checks passed, but guest boot and provisioning need separate implementation. Use simulated management interfaces where appropriate.
4. Hardware: separate lab validation for FPGA cards, NIC behavior, and Cisco switches. Simulations do not establish physical hardware correctness.

The persistent lab's stop/start took 7.62/48.2 seconds before full-stack deployment; PVC persistence and post-resume smoke checks passed. All owned fixtures were reclaimed, but minikube's known post-restart reclamation issue requires a stable storage/reclaim choice before full-stack destructive lifecycle tests; see [evidence and limits](../ops/kubernetes/README.md).

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

Start by inspecting `platform/example_output`, which contains node, FHS, and switch samples. Coverage and suitability have not yet been verified.

Collect raw exporter output and a short Prometheus time series from representative servers and switches. Include device model, exporter version, units, and expected behavior. A single snapshot cannot validate rate calculations or historical panels. Sanitize identifying values consistently while preserving label relationships. Do not commit credentials.

Use those captures as repeatable fixtures, with additional cases for outages, missing metrics, and counter resets. Keep fixture provenance and distinguish captured data from synthetic cases.

## Next decisions

- Budget VM memory alongside the platform before guest provisioning.
- Choose the runner and pipeline configuration.
- Map roles to container, VM, simulated-device, or physical-lab tests.
- Extend selected monitoring checks with representative telemetry and expand the accepted [manage_users container test](../roles/manage_users/molecule/default/README.md) to other roles.

## Role test findings

The original inspection found an absent collection path, missing Molecule dependency and stale role imports. The integrated [manage_users scenario](../roles/manage_users/molecule/default/README.md) now has isolated dependencies and a shared runner; fresh state, unchanged rerun, changed sudo policy and observed drift repair passed. Other role scenarios and their upgrade behavior remain unvalidated. Existing root CI runs lint/docs. See [source map](../wiki/sources.md).

| Role | Observed test concern |
|---|---|
| DPDK | Removes the build/source tree and rebuilds each run. |
| FHS exporter | Forces pip reinstallation and removes the installer archive. |
| gRPC | Regenerates Poetry locks/installs with change reporting suppressed; service templates force changes/restarts. |
| BIST | Repeats compilation/installation; offline clean builds ignore compilation failures. |
| GitLab runner | Python 3.12 pydantic directory is an existence marker, not version verification. |
| Venvs | Existing Python executable guards creation; interpreter changes need explicit handling. |
| BittWare SDK | Already compares installed/requested package versions; preserve that logic. |

Proposed matrix: fresh install, unchanged rerun, A-to-B upgrade and recovery/drift. Measure timings and effects beyond Ansible changed counts. Continue from the accepted users scenario to exporter, BIST and DPDK. No production role fixes are claimed. Evaluate community Prometheus/Node Exporter roles, built-in pip and Helm modules against offline/upgrade requirements before reuse. Keep SKA orchestration; Kubespray is an option, not an agreed migration.
