# hwmanage lab acceptance

2026-10-31: authenticated against the existing delivered chart's NetBox 4.7.0
in `fhs-inventory-alignment` on dragonvm, with Kubernetes context explicitly
`fhs-test`. Its NetBox, worker, PostgreSQL and Valkey pods were Ready.

`lab_acceptance.py` exercised the delivered standalone Ansible import task in
`playbooks/netbox/ironic_import.yml`, its independent `ironic_minimal.py` entry
point, native OpenStack SDK and existing REST helper against that NetBox.
The fixture entered at the import task: package installation was not exercised.
A loopback synthetic Ironic HTTP endpoint served API discovery, node listing and
saved inspection; a private test-only `ipmitool` executable returned synthetic FRU.
no physical BMC, Linux host or lifecycle operation was contacted.

Observed passes:

- Standalone Ansible task persisted the initial device without the hwmanage CLI.
- Native SDK read the synthetic Ironic API and launched the controller FRU process.
- Standalone import used a fixed UUID selection rather than relisting all nodes.
- `hwmanage inventory import -i ironic --all --plan` resolved UUIDs, ran the native
  playbook, preserved private environment paths and completed successfully. Its
  check-mode package task was skipped; the read-only FRU process still ran.

- An unnamed Ironic node became a device named by verified FRU Product Serial.
- The Ironic UUID persisted on the device.
- Only provisioning and BMC interfaces were created, with native primary MAC.
- BMC addressing used native out-of-band IP; no Linux primary IP was inferred.
- Repeated import retained one device ID.
- An operator's name, primary IP, tags and status survived repeat import.
- A conflicting Ironic UUID failed before writes.

All synthetic devices, addressing and fixture parent objects were removed.
The shared `ironic_uuid` custom field and provisioning-interface tag are importer
schema and remain available. Existing platform credentials were read privately;
no secrets were printed or copied into the repository.

Run on dragonvm from a staged checkout with an Ansible Python environment containing openstacksdk:

```bash
/tmp/fhs-discovery-tools-venv/bin/python \
  ops/role-tests/hwmanage/lab_acceptance.py \
  --credentials /private/netbox-credentials.json \
  --report /tmp/hwmanage-lab-acceptance.json
```

The credential file format is `{"url": "http://...", "token": "..."}`.
The harness normalizes its retained lab URL to HTTP. Do not use it against
production. It tests native API persistence and identity behavior, not physical
FRU transport, inspection agent behavior, cleaning, deployment or switch boot.

Final entrypoint run: all 11 assertions passed after correcting environment-path
forwarding in the delivered playbook. All synthetic objects were removed.
