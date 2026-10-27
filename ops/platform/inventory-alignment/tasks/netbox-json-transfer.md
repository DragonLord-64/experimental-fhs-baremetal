# NetBox JSON transfer

Goal: build a small Python CLI with `export` and `import` modes to copy NetBox
inventory between instances using a portable JSON file. Read URL/token from the
same YAML vars file used by the existing Ansible playbooks (`netbox_url`,
`netbox_token`, certificate setting). Reuse existing dependencies and authentication
conventions; support Ansible Vault files using existing Ansible facilities where
available, with clear errors and no credential logging.

User intent: carry existing manually maintained PDUs, switches and their related
inventory and network/power connections to the new instance, preserving all
writable fields within supported inventory objects. JSON replaces the previously
discussed CSV/Excel approach. This is a reusable script, not a live migration now.

Scope: `playbooks/netbox/`, focused checks under
`ops/platform/inventory-alignment/`, and corresponding validation/log notes.
Cover sites/locations/racks, manufacturers/device/module types and prerequisites,
devices, installed components and inventory items, interfaces, MAC/IP addresses,
power ports/outlets, cables and custom field definitions/values. Inspect actual
API schemas and existing code rather than guessing payloads. Preserve writable
nested data and relationships using portable identities; never reuse source IDs
as destination IDs. Resolve dependencies, including deferred primary-IP and
cable references. Handle pagination and prefixed URLs. Inventory plugin objects
must be supported or explicitly reported as unsupported, never silently lost.

Import creates missing objects and updates matching objects from supplied fields.
It never deletes records absent from the file. Missing fields preserve destination
values; explicit null/empty writable values follow documented update semantics.
Ambiguous matches and occupied cable/IP/MAC ownership are reported and preserved,
not silently reassigned. No DELETE calls. Distinguish read-only/generated fields
from supported writable fields and report nontransferable data and version/plugin
incompatibilities. Do not promise full database/history/credentials migration.
Provide a useful preview/dry-run and clear partial-failure summary; reruns converge.
Protect exported private inventory with restrictive file permissions and omit
API credentials from exports/logs. Document concise copyable usage.

Acceptance:
- Focused sanitized source/destination fixture has different IDs and includes
  switch management IP, PDU outlets, dual server PSU connections and network cable.
- Export/import preserves supported writable fields and resolves relationships;
  rerun updates without duplicates, existing unrelated records survive.
- Missing/ambiguous references and occupied endpoints produce actionable reports;
  preview makes no writes and no operation issues DELETE.
- One focused native transfer check against disposable records on the existing
  delivered-chart lab, explicitly context `fhs-test`, after inspecting services.
  Reuse existing helpers/services; no new cluster or broad harness project.
- Record exact checks and actual outcomes, plus unsupported objects/fields.

Exclusions: no production access or migration, switch/PDU control, discovery
changes, provisioning/cache fixes, independent review agent or broad refactors.
Preserve user work and the accepted hardware-import baseline. Controller owns
configured checks; add only focused behavior checks that they do not cover.
Stop with a concrete limitation if broad API compatibility exceeds the budget;
never label a partial transfer as all-field success. User reviews the result.
