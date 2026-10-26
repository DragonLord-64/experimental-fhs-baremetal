# Controller resources and inventory

Current accepted behavior: [working hardware import baseline](netbox-import-baseline.md).
The dated records below retain earlier decisions and validation boundaries; the
baseline supersedes their identity, suffix-matching and removal policies.

Resource-directory changes remain proposed. NetBox import/reconciliation is
implemented within the acceptance boundaries below. No resource drive, secrets
or production inventory was migrated by this wiki update.

## Resource drive

Keep a configurable resource root on the Ansible controller:

```text
<resource-root>/
  packages/<component>/<version>/
  secrets/                       # restricted; encrypted where practical
  telemetry/                     # sanitized captures with provenance
  fixtures/                      # test-only inputs and credentials
```

Proposal: keep a Git manifest of package versions, filenames and checksums;
preserve immutable package bytes on the drive and verify prerequisites before
target changes. Encrypt secrets with Ansible Vault, keep its unlock credential
separately and back up the drive independently of Git. Tests use their own
resource root and credentials. This layout has not been rolled out.

## NetBox direction

| Owner | Values |
|---|---|
| NetBox | Device/site facts, native interfaces/IPs/cables, profile membership and selected non-secret overrides |
| Inventory plugin | Serial-tracked hardware assets and their installed/stored/faulty state |
| Git | Role defaults, reusable profiles, policy, manifests and approved release definitions |
| Protected controller storage | Secrets, Vault unlock material, local package bytes and resource paths |

Assign one authority per value and inspect resolved precedence before deployment.
Use config contexts/custom fields for selected non-secret configuration, not
private credentials. Keep `group_vars/all.yml` small. Fast tests use sanitized
fixtures; changed importer/runtime behavior also needs the
[delivered-chart/native-importer lab acceptance](../ops/platform/inventory-alignment/README.md).

The imported source did not identify its NetBox chart version. The lab selected
chart `8.3.67` and NetBox `4.7.0`; that is [lab provenance](../ops/platform/README.md),
not identification of the user's production version. `netbox.netbox` is the
control-machine Ansible collection. Inventory `2.7.1` and Topology Views `5.0.0`
are separate server plugins; see [asset acceptance](../ops/platform/inventory-alignment/VALIDATION.md)
and [topology acceptance](topology-import.md).

### Small profile mapping example

Proposed example, not applied: add tag `ubuntu24-cis-production` and this entry
under the existing inventory plugin's `groups` mapping, preserving other entries:

```yaml
groups:
  ubuntu24_cis_production: "'ubuntu24-cis-production' in (tags | map(attribute='slug') | list)"
```

NetBox selects group membership; Git keeps policy in
[inventory/dev_env/group_vars/ubuntu24_cis_production.yml](../inventory/dev_env/group_vars/ubuntu24_cis_production.yml).
Inspect actual plugin tag shape and `ansible-inventory --graph` against an
authorized inventory before deployment. Config-context values do not establish
precedence over every other variable source.

### Import decision — 2026-10-22

The user-confirmed workflow is discover/import, edit intended configuration in
NetBox, apply with Ansible, then verify. Intentional reimport updates successfully
observed facts. Chassis serial identifies physical hardware; IP supplies access.
Failed probes do not establish absence, and a reused hostname cannot authorize
chassis replacement.

The [current procedures](../docs/src/playbooks/development.md#asset-reconciliation)
implement serial-matched assets, installed-record replacement and parent journals:

- Replacement deletes/recreates the installed module record in its actual bay,
  while the old serial-tracked asset survives separately. This supersedes keeping
  removed modules as uninstalled records.
- Removal defaults off. Explicit complete scopes plus successful collection are
  required; failed/partial/uncollected sections and hosts outside the scan are
  preserved. A complete empty section differs from unavailable output.
- Cabled replacement is refused for review. Old connections are not copied to
  new hardware as verified facts. Native topology now joins observed LLDP peers
  or unique exact DAC serial pairs; [unresolved endpoints preserve cables](topology-import.md).
- Parent device journals record serials, bay and result. REST reconciliation spans
  multiple requests, so inspect partial state before retrying. Journals depend on
  the surviving parent and backups; change logs have separately configured
  [retention](../platform/charts/fhs-platform/CONFIGURATION.md#netbox).

Asset/history and FRU acceptance is [recorded](../ops/platform/inventory-alignment/VALIDATION.md);
physical discovery and production readiness are not inferred from synthetic data.

### Discovery inventory boundary — proposed

The accepted design uses standard YAML Ansible inventory (`all`/`hosts`/`children`,
`ansible_host`) plus structured identity, component, interface, verified-cabling
and per-section completion fields. A versioned hardware contract and semantic
round-trip acceptance remain unimplemented. The planned boundary is hardware
read → normalized inventory YAML → controller-side NetBox reconciliation.
Current entrypoints discover live facts and call native modules directly; they
do not yet implement this general offline import boundary.

Export reuses [the existing NetBox inventory plugin](../inventory/dev_env/netbox-inv.yml)
with normal Vault authentication. On the authorized controller, the proposed
private output command is:

```sh
ansible-inventory -i inventory/dev_env/netbox-inv.yml --list --yaml --output /private/inventory.yml
```

Do not run it as a documentation check: it polls the configured inventory.
Current settings request interfaces, IPs, config contexts, flattened custom
fields, modules and inventory items. Inspect actual output before defining field
mappings or claiming cabling round-trip coverage. NetBox export is not fresh
physical verification and cannot authorize absence removal. The
[Bifrost export](../playbooks/netbox/bifrost_export.yml) remains separate
provisioning output. No new general inventory exporter is planned.

### Spare assets — trial 2026-10-23

The user selected a free, openly licensed extension permitting commercial use.
The isolated [MIT Inventory trial](../ops/platform/inventory-trial/README.md)
recorded 17 API checks for serial, location, faulty state and asset survival after
module deletion. It was followed by the integrated asset acceptance above;
importer integration is no longer pending.

Manual standalone DAC stock/quarantine does not invent a native cable endpoint.
The trial's manual faulty status did not enforce reuse prevention; the current
importer explicitly refuses installation of a faulty asset pending review.
Neither result proves a complete operational stock workflow or physical hardware.
