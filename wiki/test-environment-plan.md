# Experimental test environment plan

Evidence reviewed 2026-10-25 at private development `4a0c5cf`. This page combines
lab status, the original handoff's role findings and remaining work. Results are
dated observations, not fresh checks of service health. Source ancestry and
preserved history are in the [source map](sources.md).

## Compute and budget

Use the local Linux server for editing/lightweight checks and dragonvm for lab
integration, orchestrated locally. Initial 2026-10-21 inspection found four local
CPU cores/16 GB RAM and eight guest CPUs/11 GiB RAM. Available RAM, swap and disk
figures from that inspection are not current capacity guarantees.

Use the existing `fhs-test` profile; name its context explicitly because the
default is `monitoring`. The lab uses Docker/minikube and containerd. The lifecycle
helper requests 6144 MiB for new profiles, but the
[installation-home acceptance](../ops/platform/landing-page/README.md) later
retained an 8 GiB cluster-container limit / 10 GiB memory-plus-swap. Inspect actual
capacity before integration; do not treat the helper's default as the current limit.

[Lab operations](../ops/kubernetes/README.md) own access, wake troubleshooting
and application lifecycle. No second cluster is needed. Keep both host operating
systems running; retain data and make external backups. Cloud target is zero,
monthly ceiling below US$10, with no purchase authorized.

## Recorded validation

| Boundary | Observed evidence | Remaining limits |
|---|---|---|
| Task pipeline | [Original authenticated smoke and current fake-worker/manager checks](../ops/agent-pipeline/VALIDATION.md); one-worker workflow now replaces three-worker review | No new authenticated model smoke for the queue/manager; configured CI is not a pass |
| Kubernetes/storage | [Node, DNS, Service, PVC and bounded stop/start checks](../ops/kubernetes/README.md); [platform retained data](../ops/platform/VALIDATION.md) | Single-node hostPath, no HA/backup guarantee; historical timings do not predict current recovery |
| Native NetBox/chart | [Assets, serial identity, replacement, journals and optional FRU](../ops/platform/inventory-alignment/VALIDATION.md) | Scoped synthetic lab acceptance; not physical FHS/Nexus discovery or production ingress/TLS |
| Topology | [LLDP/DAC collector, native cable and Topology Views acceptance](topology-import.md) | Synthetic read-only device commands; physical LLDP/EEPROM behavior unverified |
| Discovery/home | [Full-chart discovery/home acceptance](../ops/platform/discovery-portal-setup/VALIDATION.md), [cached installation-home acceptance](../ops/platform/landing-page/README.md) | Preserved credentials/PVCs/scales; no production/TLS/hardware claim |
| Logging | [Actual finite Filebeat filestream ingest/Discover](../ops/platform/logging/validation.md); [delegated setup fixture](../roles/filebeat/README.md#elasticsearch-setup) | Device journald/live delegated setup unverified; chart setup currently opt-in |
| Users role | [Fresh install, unchanged rerun, sudo policy and drift repair](../ops/role-tests/manage_users/molecule/default/VALIDATION.md) | Disposable container only; not broad role coverage |
| Provisioning | [Restricted Ironic API and KVM VM/vCPU creation](../ops/provisioning/README.md) | No conductor, DHCP/PXE, guest boot or physical provisioning |
| Dashboards | [Static demo and observed-data evidence](latest-changes.md) | Synthetic demo cannot close observed telemetry/navigation gaps |

The early minikube storage-reclamation issue is historical: the platform adopted
static retained volumes. Deleted claims still need explicit operator recovery;
nominal PV size is not a disk quota. Do not infer disaster recovery from the
recorded application-level stop/start test.

Chart Filebeat setup is currently disabled by default in
[values](../platform/charts/fhs-platform/values.yaml). The device role's separate
delegated setup is implemented; its fixture does not establish live Elasticsearch
or device journald acceptance. The [dated log](LOG.md) records these changes in order.

## Checks by change

Follow the [task workflow](../ops/AGENTS.md): docs/link checks for documentation,
focused syntax/behavior checks for the changed source, and existing delivered-chart
plus native-importer lab acceptance when that runtime boundary changes. The
controller owns configured checks; avoid repeating them or adding test infrastructure
for a small task. Keep local and configured CI entrypoints identical.

Provisioning and kernel/network roles may need disposable VMs and isolated
networks. The source Bifrost launcher's privilege, host-network and DHCP assumptions
are not reproduced by its API fixture. FPGA/NIC/Cisco behavior requires explicitly
scoped physical-lab acceptance; hardware simulations cannot prove it.

## Role test findings

The 2026-10-21 static inspection found an absent collection path, missing Molecule
dependency and stale imports. The private users scenario now has isolated
requirements and a validated [lab runner](../ops/role-tests/manage_users/run.sh).
Official legacy entrypoints remain preserved separately. The concerns below are
historical inspection findings, not a fresh runtime audit or measured regressions.

| Role source | Original concern |
|---|---|
| [DPDK](../roles/manage_dpdk_ark_doca/README.md) | Removes build/source trees and rebuilds each run |
| [FHS exporter](../roles/manage_fhs_exporter/README.md) | Forces pip reinstall and removes installer archive |
| [gRPC](../roles/manage_fhs_grpc/README.md) | Lock/install work suppresses change reporting; templates force restarts |
| [BIST](../roles/manage_fhs_bist/README.md), [offline BIST](../roles/setup-fhs-offline-bist/README.md) | Repeated compilation; ignored offline build failures |
| [GitLab runner](../roles/manage_gitlab-runner/README.md) | Python 3.12 pydantic directory is not dependency-version verification |
| [Venvs](../roles/manage_venvs/README.md) | Existing interpreter alone guards creation |
| [BittWare SDK](../roles/manage_bittware_sdk/README.md) | Existing version comparison is useful and should be preserved |

Proposed follow-up matrix: fresh install, unchanged rerun, A-to-B upgrade and
observed drift/recovery, measuring timings/effects as well as Ansible changes.
Start from the users harness and prioritize exporter/BIST/DPDK only when assigned.
Evaluate community Prometheus/Node Exporter roles, pip and Helm modules against
offline/upgrade requirements first. Kubespray remains an option, not an agreed migration.

## Remaining work

- Budget memory and implement isolated guest boot/provisioning before broader VM tests.
- Define the [normalized discovery-inventory boundary](resource-layout.md#discovery-inventory-boundary--proposed).
- Establish representative telemetry/time-series coverage and close the observed-dashboard gaps.
- Select broader role coverage and runner access; track actionable scope and
  acceptance in GitHub issues rather than creating work from historical findings.
