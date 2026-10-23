# Controller resources and inventory

Proposed layout, discussed 2026-10-21. Existing resource storage remains in use; no directories or credentials have been migrated.

## Resource drive

Keep a configurable resource root on the Ansible controller, with separate directories:

```text
<resource-root>/
  packages/<component>/<version>/
  secrets/                       # restricted; encrypted where practical
  telemetry/                     # sanitized captures with provenance
  fixtures/                      # test-only inputs and credentials
```

Commit a package manifest containing versions, filenames, and checksums to Git. Preserve immutable versioned package bytes on the drive. Validate required files and checksums before changing targets. Encrypt secrets with Ansible Vault and keep its unlock credential separately. Back up the resource drive independently of Git. Test environments use a separate resource root and test credentials.

## NetBox direction

The imported source did not identify its NetBox chart version. The private lab selected and verified chart `8.3.67`, image `v4.7.0`; see [platform provenance and overrides](../ops/platform/README.md). This does not identify the user's production chart version.

- Use native NetBox objects for devices, sites, roles, platforms, IP addresses, interfaces, MAC addresses, and cabling where supported by the installed version.
- Config contexts can hold non-secret site/role/device configuration. Use explicit custom fields for additional structured properties where appropriate.
- Use the NetBox Ansible inventory plugin to compose connection variables and groups. Inspect the existing `inventory/dev_env/netbox-inv.yml` before changing mappings.
- Keep credentials in Vault/protected storage. NetBox can hold references to secrets rather than their values.
- Keep reusable role defaults, implementation details, and controller-local resource paths in Git or runner configuration. Package manifests and approved release definitions benefit from Git review.
- Avoid duplicate authorities: assign one owner to each value and define precedence. Test resolved inventory before deployment.
- Tests should use recorded, sanitized inventory fixtures rather than depend on a live NetBox service. Record NetBox inventory snapshots or revisions with deployment evidence when feasible.

References: [NetBox config contexts](https://netbox.readthedocs.io/en/stable/models/extras/configcontext/), [Ansible inventory plugin](https://docs.ansible.com/projects/ansible/latest/collections/netbox/netbox/nb_inventory_inventory.html).

### Small profile mapping example

Proposed example; not applied to the inventory. Give a device the NetBox tag slug `ubuntu24-cis-production`. Add this entry under the existing inventory plugin's `groups` mapping (preserving its other entries):

```yaml
groups:
  ubuntu24_cis_production: "'ubuntu24-cis-production' in (tags | map(attribute='slug') | list)"
```

Ansible then loads `inventory/dev_env/group_vars/ubuntu24_cis_production.yml` for that group when using the adjacent NetBox inventory. NetBox selects membership; Git retains the CIS policy. Verify the installed plugin's tag representation and resolved group membership with `ansible-inventory --graph` before deployment.

Keep `group_vars/all.yml` small: genuinely global settings only. Standard profiles and reusable defaults remain in Git; NetBox supplies membership and selected overrides, with resolved precedence checked before use.

### Spare assets — trial 2026-10-23

User requires a free, openly licensed inventory extension permitting commercial use; NetBox version changes are allowed. The isolated [NetBox Inventory trial](../ops/platform/inventory-trial/README.md) uses MIT-licensed `2.7.1` with NetBox `4.7.0`. Seventeen real API checks and independent review passed: DAC assets retain serial, shelf and faulty status without an installed connection; an FPGA asset retains serial and change history after its installed module is deleted. The surviving asset identity is separate from its installed module record. Importer integration remains pending.

The DAC is a standalone asset with an inventory-item type; no native Cable association was needed for this stock-tracking trial. Status/location transitions are manual and faulty status does not prevent reuse automatically. Default change-log retention is 90 days; the trial has no maintenance worker. Recorded screenshots and synthetic fixtures do not prove physical discovery or production readiness.
