# Complete FHS QSFP, cable and placement discovery

[Issue #16](https://github.com/DragonLord-64/experimental-fhs-baremetal/issues/16).
Pipeline task: `netbox-discovery-completion-20261025` (queued).

## Goal

Complete the unified NetBox importer for the user's observed FHS/Nexus topology.
Keep Linux and NX-OS strategies behind one entrypoint. Fiber and ordinary network
connections use LLDP, including breakout interfaces. FPGA DAC connections are the
special case: identify their physical endpoints using verified cable serial data.
Keep native NetBox connections compatible with Inventory and Topology Views.

## Source evidence

Inspect current official SKA `development2` before implementing; it already has
shared defaults and the corrected NetBox credentials filename. Preserve those
changes, installed-tool conventions and source provenance. Official repositories
remain fetch-only. Read `roles/manage_bittware_sdk/tasks/bittware_venvs.yml`,
`roles/setup_fpga_host/`, `roles/manage_gitlab-runner/`, and official
`playbooks/development/output-samples.md` and `topology-discover-strategy.md`.

The user's seven original screenshots are preserved privately with SHA-256 hashes
and an index under `ops/agent-pipeline/runs/netbox-discovery-completion-20261025/evidence/`.
Read all images; the five latest images are the primary hardware evidence. Raw
images contain internal identifiers: retain privately, never commit them or copy
unsanitized transcriptions into Git. Build sanitized representative fixtures with
a consistent alias/serial/MAC mapping and document their provenance. Preserve
serial suffix relationships, repeated breakout rows, part strings, port names,
and output formatting. Do not invent fields clipped from a photo.

Observed cases to capture:

- Topology Views shows very few connections after an import; this is an outcome
  to diagnose, not proof of a precise database cable count.
- First Nexus LLDP table has three neighbors: management switch on mgmt0; FHS
  host on Eth1/30 with dotted-MAC Port ID; another host on Eth1/32.
- Second Nexus LLDP table has four neighbors: management switch on mgmt0, two
  hosts on Eth1/31 and Eth1/32, and that management switch on Eth1/33. Preserve
  the separate links, including different port-name formats.
- Linux LLDP reports a host access alias differing from its actual hostname,
  a PCI NIC interface, chassis MAC, switch SysName, management IP and an ifname
  PortID such as Ethernet1/30. Additional interface output is visibly clipped.
- BittWare QSFP output contains populated QSFP0/QSFP1 with QSFP-DD, vendor FS,
  part QDD-400G-PC01, vendor serials ending -2/-1, vendor revision/date,
  cable_length and presence. It also includes a misleading-looking VCSEL string:
  do not classify the known DAC using that field alone. Verify cable identity
  from supported vendor/part/evidence, not arbitrary substring heuristics.
- Official SDK samples add empty/Removed QSFP ports and repeated serials across
  switch breakout lanes. Test these together with the user-supplied evidence.
- Earlier screenshots show Inventory API 404 and the plugin's initial undrawn
  page. Distinguish prerequisites/filter state from failed discovery.

## Required implementation

1. Align read-only BittWare commands with the configured SDK venv, SDK root and
   BittWare user. Verify executable/Python package/USB access and report specific
   failures. Reuse existing role variables/conventions instead of divergent
   hardcoded paths. SDK installation belongs to the provisioning role; discovery
   must not silently pip-install packages or alter firmware/ports.
2. Discover physical QSFP interfaces dynamically from actual card/port reports,
   retaining empty ports. Keep module presence distinct from interface existence.
   Import observed vendor, model/part, serial, revision, cable length and other
   useful reported module metadata through the appropriate Inventory/native
   objects; do not discard everything except serial or invent missing identity.
3. Capture physical connector and breakout relationships. Distinguish logical
   lanes from a physical fanout cable; repeated lane observations must not create
   duplicate physical DAC cables. Use a NetBox-supported model validated against
   the installed version, with native interface IDs and graph visibility.
4. Correct FPGA DAC classification and serial matching for these cases. Prefer
   exact full serials; any vendor-specific endpoint-suffix rule must be explicit,
   evidence-backed and collision-safe. Do not blindly strip -1/-2 or assume
   same-prefix serials are one cable. Preserve occupied/conflicting connections.
   Fiber connections use LLDP; optical module serials never identify the fiber.
5. Resolve LLDP device/interface identities using verified hostname/access-alias,
   name/chassis/MAC evidence. Handle dotted MAC port IDs, supported JSON shapes,
   existing peers outside the selected import scope, and empty/failed probes.
   Import or resolve existing peer interfaces only from actual observations.
   Report unsupported peers instead of inventing hardware or adding another
   switch collector merely for the management switch in the screenshots.
6. Extend optional `/etc/server-info.yaml` metadata while retaining existing
   site/role/location/rack behavior and existing files. Add optional `rack_unit`
   and exactly identified independent server power inlet mappings, for example:

   ```yaml
   site: Example Site
   role: FPGA_HOST_SERVER
   location: Example Room
   rack: Rack01
   rack_unit: 12
   power_ports:
     - name: PSU1
       pdu_serial: SYN-PDU-A
       pdu_port: "12"
     - name: PSU2
       pdu_serial: SYN-PDU-B
       pdu_port: "8"
   ```

   Resolve each PDU by serial, each outlet by its name on that PDU, and connect
   native server power ports to those native PDU outlets. Each inlet may connect
   to a different PDU. Reject ambiguous/missing PDU/outlet identities, duplicate
   or occupied terminations, invalid rack units and placement conflicts without
   guessing. Missing new metadata must preserve existing NetBox placement/power
   records. No automatic PDU discovery or control is requested. Mounting face,
   tenant/team, purpose and subsystem fields were suggestions, not agreed scope.
7. Add concise per-device/port diagnostics: expected/discovered/skipped probes,
   source identity, parsed ports/modules, candidate matches and precise omission
   reasons. Retain raw captures privately and provenance; publish sanitized test
   reports. Keep facts/compare/check read-only and apply idempotent.
8. Keep operational defaults in `playbooks/netbox/defaults.yml` and preserve the
   official credentials path `/provision/files.d/credentials/mid-cbf-hw-netbox.yml`.
   Document the metadata schema and normal compare/apply use briefly.

## Scope and exclusions

Allowed: `playbooks/netbox/`, relevant BittWare role defaults/tasks only when
needed to reuse existing environment configuration, focused tests/fixtures and
acceptance under `ops/platform/inventory-alignment/`, relevant operator docs and
short linked wiki evidence. Preserve unrelated edits and untracked emulator work.
Do not rewrite roles, add general inventory frameworks, bypass conflicts, alter
production devices, contact screenshot addresses, purchase resources, change the
pipeline controller, or push official repositories. Keep both hosts running.
No independent review agent; the user performs review. Worker does not publish.

## Acceptance and controller handoff

Provide `ops/platform/inventory-alignment/acceptance_discovery.py --dragonvm
--report /tmp/fhs-discovery-completion-acceptance.json` as one controller entrypoint.
It must run relevant real Ansible syntax/routing/discovery fixtures and native
importer acceptance against the delivered chart on the existing dragonvm
`fhs-test` cluster, explicitly naming context `fhs-test`. Inspect preserved
services and pipeline state first; follow the root wake protocol if unreachable.
Reuse protected lab credentials/retained services without exposing them. The
worker writes the harness; the controller runs it, including authorized lab-only
operations. Worker must not deploy or execute the controller checks itself.

The report must prove all seven representative LLDP links when their synthetic
peers exist; actual SDK collector task/environment/user behavior; populated and
empty QSFP ports; Inventory metadata round-trip; physical/breakout associations;
unambiguous FPGA DAC cable creation and safe ambiguous-suffix handling; partial,
failed and repeated imports; existing cable and asset preservation; rack-unit
placement; PSU1/PSU2 cables to distinct PDUs; missing/ambiguous/occupied power
failures; facts/compare/check without writes; and unchanged repeated apply.
Verify the imported network connections in actual authenticated Topology Views
and check Inventory asset behavior. Do not substitute one preassembled synthetic
switch observation for exercising the Nexus parser/task boundary. No physical
hardware success may be claimed from synthetic fixtures or screenshots.

Completion requires the controller report to pass; one-cable smoke or unit-only
success does not complete this scope. If scope/time or a tool boundary blocks
acceptance, preserve work and give a precise handoff rather than weaken checks.
