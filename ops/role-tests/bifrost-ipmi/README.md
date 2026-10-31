# Bifrost adapter and remote IPMI checks

Run with the provisioning environment’s Ansible Python dependencies installed.

```bash
python3 -m unittest discover -s ops/role-tests/bifrost-ipmi -v
```

Uses synthetic node data to check SSH/BMC mapping, Redfish-address conversion,
explicit IPMI port, alias selection, shared credentials, missing fields and
ambiguous mappings. No BMC, NetBox or host is contacted by these unit tests.

Live wrapper/native-importer checks use the existing delivered-chart NetBox on
`dragonvm`, context `fhs-test`. The controller installs real `ipmitool`; a
synthetic executable verifies password-in-environment arguments and returns FRU,
BMC firmware and LAN fixtures. This validates Ansible delegation and parser/API
integration, not IPMI wire compatibility with physical BMCs. Keep source
inventories, credentials and raw logs outside Git.
