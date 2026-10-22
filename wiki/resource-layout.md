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

The user reports an existing Helm-based NetBox deployment; installed version and chart have not been verified.

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
