# Nexus management IP import

Goal: a discovered Nexus switch displays its observed management address as its
NetBox primary IPv4 (or primary IPv6 when applicable), attached to its actual
management interface.

Evidence: user reports imported switches have no visible primary/management IP.
`playbooks/netbox/tasks/import_nexus.yml` writes chassis, versions, components
and topology interfaces but has no address reconciliation or primary-IP step.
The importer README explicitly records missing Nexus MAC/IP support.

Scope: `playbooks/netbox/`, focused existing inventory-alignment fixtures/checks,
and the corresponding README and validation/log notes. Reuse existing native
NetBox modules/helpers. Collect actual NX-OS management interface/address output;
do not infer a verified management address or prefix from the SSH target.

Acceptance:
- Representative NX-OS output creates the management interface and correctly
  prefixed address, assigns it to that interface and sets the switch primary IP.
- Wire into the existing `interfaces`, `ips`, default/apply and preview behavior;
  an `ips`-only run resolves the existing parent without creating a chassis.
- Missing/failed/ambiguous observations preserve existing addresses and primary
  selection with useful diagnostics. Conflicting address ownership is protected.
- Repeated unchanged import creates no duplicate interfaces or addresses.
- Check mode/compare make no writes; facts collection makes no NetBox mutations.

Checks: worker selects existing focused parser/task checks and importer syntax
checks, then one small native reconciliation check on the existing delivered-chart
lab, explicitly using context `fhs-test`. Record exact commands and results.
Do not build another harness or rerun full asset lifecycles. Inspect existing lab
services before use and follow the wake protocol if necessary.

Exclusions: no switch configuration changes, VLAN import, provisioning/cache
repairs, production access, broad stage refactor or removal policy changes.
Preserve the working hardware-import baseline and unrelated work.

Limits: synthetic/native lab checks do not prove physical NX-OS discovery;
report hardware validation separately. User reviews the result.
