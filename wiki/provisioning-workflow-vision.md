# TerraBox discovery to provisioned inventory

Confirmed operator vision, 2026-10-31. This is the target design, not a claim that
the CLI or end-to-end workflow is implemented. Bifrost is the discovery/deployment
environment; Ironic owns its node database and lifecycle state. NetBox owns
reviewed names, intended addressing, role/tags and deployment configuration.

## Operator workflow

1. Plug in a TerraBox on the provisioning network. Unknown-node PXE discovery
   boots IPA and saves inspection data in Ironic. No cleaning or OS deployment
   follows discovery automatically.
2. Run one import command in the provisioning container. Create/update the minimal
   NetBox record from Ironic: verified system serial, default name equal to serial,
   BMC address and the provisioning NIC/MAC. Do not import the other host NICs,
   modules, cables or assign the temporary discovery lease as Linux primary IP.
   Represent the BMC using native NetBox out-of-band addressing and the necessary
   management interface/IP association.
3. Review the device in NetBox. Assign the intended Linux primary IP to the
   provisioning interface, rename if desired, apply role/tags and select the
   shared image/deployment profile. Preserve physical identity across renames.
4. Explicitly enroll/prepare, optionally clean, then deploy, then provision.
   The operator normally runs three lifecycle commands after the initial import.
5. Optionally collect the full inventory after provisioning has installed tools.
   Enrich the existing NetBox device with interfaces, MAC/IP associations, modules,
   card/component serials, OS/firmware versions and observed cable identifiers.

Proposed CLI examples only; `fhs` is a placeholder name to design with the user:

```bash
fhs import-discovered --host <IRONIC_UUID>

# After reviewing the record in NetBox:
fhs enroll --host sys1412 --clean
fhs deploy --host sys1412
fhs provision --host sys1412 --get inventory

# One explicitly selected process for the lifecycle sequence:
fhs run --host sys1412 --clean --get inventory

# Explicit fleet operation; never the default:
fhs provision --all

# Equivalent local input when NetBox is unavailable:
fhs provision --inventory /provision/files.d/recovery.yml --host sys1412
```

The source selector, CLI name, multi-host argument form and inventory-collection
spelling are proposals. Required behavior is explicit targeting, optional cleaning,
optional collection and one process capable of chaining the lifecycle steps.

## Required behavior and ownership

- Every operational command requires a specific host/node selection or `--all`;
  neither supplied is an error before any action. Reject combining selectors,
  empty matches and ambiguous records. NetBox profile filters must not expand the
  requested scope. Resolve the target set once for a combined run, retaining
  immutable node/device IDs rather than depending on mutable hostnames.
- The initial import works before Ubuntu or SSH exists. Read Ironic's API and
  saved inspection records, not the Linux discovery playbook. Use inspected
  identity when its source establishes the required FRU Product Serial; otherwise
  use controller-side IPMI with protected BMC credentials. Conflicting serials
  require resolution. Never infer physical identity from an Ironic name alone.
- Default NetBox name equals the verified serial; preserve an operator's later
  name, IP, tags and deployment settings on reimport. Record the Ironic UUID for
  future matching; detect duplicate chassis and UUID/serial conflicts.
- Prefer the inspection boot MAC matched to a discovered motherboard NIC. A
  connected NIC alone is insufficient. If boot evidence is missing or the match
  is not an eligible onboard NIC, stop for review. Hardware qualification rules
  still need defining; no PCI address/driver pattern is assumed universal.
- Shared BMC credentials can live in protected controller secrets, with per-node
  overrides. Unknown discovery does not promise to recover BMC passwords. Keep
  credentials out of NetBox config contexts, CLI arguments and logs.
- Shared NetBox config contexts describe the image URL/checksum and boot/network/
  root-device policy for tags/roles; device context may override them. Reuse the
  existing provisioning-interface tag, primary IPv4 and native oob_ip mapping.
  Clearly distinguish the deployed Linux IP from Ironic's temporary DHCP lease.
- `enroll` means reconcile/register if missing, then prepare the node. An already
  auto-discovered node must not be registered a second time. Move an eligible node
  to `manageable`; execute explicit cleaning there only for `--clean`; then
  `provide` to make it available for deployment. Cleaning remains disabled by
  default (`cleaning: false`/effective per-node policy). Verify policy before
  transitions; preparation alone must not accidentally enable automatic cleaning.
- Explicit deployment writes the OS. Reject incompatible/active/transient states
  instead of undeploying or reimaging automatically. A failed stage stops that
  node's later stages. Combined runs report per-node progress/failures and do not
  blindly repeat destructive operations on retry. These scripts never alter the
  orchestration server's power state.
- Provisioning dispatches FHS/TerraBox and Nexus hosts to their applicable roles
  and connections. FHS includes the established roles and Ubuntu hardening policy;
  preserve the explicit `ubuntu24-hardening` membership rule rather than applying
  Linux hardening to every device role. Switches never run Linux/SDK tasks or
  enter the bare-metal image lifecycle. Reject incompatible lifecycle selections.
- Inventory collection is opt-in and normally skipped, using an explicit wrapper
  option mapped to a `never`/named Ansible tag. Standalone scoped collection remains
  possible. Complete provisioning/SDK installation before SDK-dependent reads.
- NetBox and Ironic sources are additive. Preserve basic YAML input for lifecycle
  and provisioning tasks, outside the repository by default, with equivalent
  settings and separate Vault secrets. Provide a portable export/snapshot of
  approved configuration. Select fallback explicitly; do not silently use stale
  inventory after a service failure. A NetBox outage must not block local-YAML
  deployment/provisioning. An Ironic outage still prevents Bifrost deployment;
  existing systems can be Ansible-provisioned without it. NetBox writes can only
  complete when NetBox is reachable; retain private collection output for an
  explicit later import if offline collection is supported.

## Current evidence and gaps

| Existing source/evidence | What remains |
|---|---|
| Operator supplied a real IPA inspection for a TerraBox: system vendor serial, BMC IP, UEFI boot MAC, complete NIC list and exactly one PXE-valid interface. Another non-provisioning NIC also had carrier. | Unknown-node discovery still needs a physical end-to-end test. Confirm FRU provenance and model; the observed product_name was a date/OEM placeholder. |
| [YAML Bifrost adapter](../playbooks/netbox/bifrost_import.yml), [remote IPMI probe](../playbooks/netbox/library/fhs_ipmi_probe.py) and [identity parser](../playbooks/netbox/filter_plugins/fhs_inventory.py) | Add an Ironic API source and a minimal pre-OS NetBox importer. Current adapter explicitly requires a node file and the native full importer uses SSH. |
| [NetBox exporter](../playbooks/netbox/bifrost_export.yml) | Reuse mapping/validation, but replace device-type-wide file export as the operational bridge with exact target selection and direct Ironic reconciliation. Preserve file export for fallback. Merge shared config context and track UUID/serial, not just names. |
| [NetBox Ansible inventory](../inventory/dev_env/netbox-inv.yml) | Its active/has-primary-IP filter is appropriate for running hosts, not initial unaddressed discovered nodes. The initial import/prepare path needs its own API queries. Ensure role/policy membership and Linux SSH inputs are composed from approved NetBox records. |
| [Existing lifecycle helper](../scripts/enroll-deploy-inventory.sh) | It chains enrollment/deployment without the proposed explicit host gate. New CLI must dispatch separate actions, default to no cleaning, and reject unscoped runs. No automatic reuse of this broad helper. |
| [Provisioning entry point](../playbooks/provision.yml), [site roles](../playbooks/site.yml), [Nexus configuration](../playbooks/switch-poap/) | Compose a mixed-family provisioning entry point, retain family isolation and replace host_vars-file assumptions in preflight. Validate its effective scope before application. |
| [Detailed NetBox importer](../playbooks/netbox/netbox_import.yml), [collection tasks](../playbooks/netbox/tasks/system.yml), [topology](topology-import.md) | Attach optional post-provision collection. Preserve established identity/assets and conflict handling. No invented connections where LLDP/EEPROM/manual evidence is absent. |

The source paths above establish reusable code, not completion of the proposed
workflow. The user's reported certificate/environment checks passed before the
ongoing Bifrost install; that does not establish current DHCP/discovery success.
Raw screenshots and private host details stay outside Git. Observation structure
is captured here without copying credentials or a live server list.

## Delivery sequence and acceptance

1. **Prove unknown discovery.** Complete the current DHCP setup, then on an
   explicitly selected disposable node demonstrate unknown-MAC PXE boot, a new
   Ironic registration and saved inspection. Record actual state and interface
   provenance; discovery must not clean disks or deploy an OS.
2. **Minimal import.** Implement Ironic read + optional remote FRU verification +
   native NetBox upsert. Verify one observed discovery shape, repeat import,
   renamed-device preservation, boot-MAC ambiguity and identity conflict handling.
   Run one focused integration against the existing chart NetBox. Require no SSH.
3. **Approved configuration and target selection.** Define shared deployment
   profile fields, YAML equivalent and secrets lookup. Build the small CLI target
   resolver/plan output. Prove missing selector fails, one target stays one target,
   `--all` is explicit, and unavailable NetBox does not block an explicit YAML run.
4. **Lifecycle bridge.** Wire enroll/manage/inspect/optional-clean/provide/deploy
   using the same normalized input. Demonstrate the explicit-clean boundary,
   state checks and failure stop behavior on isolated disposable hardware/VMs.
   Existing deployment safety and host-power restrictions continue to apply.
5. **Provision and collect.** Dispatch Nexus/FHS provisioning and optional named
   inventory stage. Test family separation, no inventory collection by default,
   one-host scope and preservation of operator-approved IP/name during enrichment.
6. **Combined run and measured optimization.** Chain the same tested stages with
   progress and actionable failure summaries. Measure per-stage timings first;
   reuse collected facts/probes within a run, avoid repeated whole-inventory
   fetches and use bounded concurrency where API/identity ownership permits it.
   Do not skip required FRU/identity checks or weaken reconciliation to save time.

Create actionable implementation issues with the relevant slice and focused
acceptance before dispatching work. This note captures the goal and sequencing;
it does not authorize changes to deployed hardware or make an implementation
schedule commitment. Start with discovery proof and minimal import, then extend
the same contracts instead of building a separate parallel provisioning system.

## External references

- [Ironic discovery](https://docs.openstack.org/ironic/2026.1/admin/inspection/discovery.html)
- [Inspection data](https://docs.openstack.org/ironic/2026.1/admin/inspection/data.html)
- [Manual and automatic cleaning](https://docs.openstack.org/ironic/2026.1/admin/cleaning.html)
- [Bifrost inventory inputs](https://docs.openstack.org/bifrost/latest/user/howto.html)
- [NetBox config context](https://netbox.readthedocs.io/en/stable/models/extras/configcontext/)
