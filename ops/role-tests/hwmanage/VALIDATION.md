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

2026-10-31 relocation check: all 11 assertions passed again using the application
under `hwmanage/`, against the same running chart and explicit `fhs-test` context.
The existing retained credential URL's port-forward had expired; a temporary
loopback service forward restored test access and was stopped after the run.
The harness cleaned up its synthetic objects. The tracked default settings and
explicit local override were separately covered by the focused contract suite
(35 passed under the Ansible environment). This does not establish physical
BMC behavior or select the site's NetBox IDs/onboard interfaces.

2026-10-31 Bifrost folder follow-up: all 11 assertions passed with the application
under `bifrost-infra/hwmanage/`. The same chart, explicit `fhs-test` context,
synthetic fixtures and temporary service forward were used and cleaned up.
This validates nested path resolution, not the user's Docker mount; Compose
YAML and the configured mount were checked locally, without recreating a container.

2026-10-31 scripts mount follow-up: all 11 lab assertions passed with the final
application path `scripts/hwmanage/`, using the same existing chart and synthetic
fixture cleanup. The extra application mount has been removed from Compose.

2026-10-31 per-node failure handling: all 11 lab assertions passed after adding
batch continuation. Mixed failure/success and duplicate-owner rejection are
covered by focused unit tests (37 total passed); the live fixture exercises
persistence and wrapper execution, not physical hardware failures.

2026-10-31 automatic boot-port selection: all 11 lab assertions passed with
`onboard_interfaces` removed from fixture settings. Unique inspected boot-MAC
selection is covered by the focused multi-NIC test; 37 focused tests passed.

2026-10-31 central controller YAML: final acceptance passed 12 assertions, adding
native NetBox inventory with a plain copied endpoint and central credential path.
Direct import and wrapper plan both use the same selected config; the fixture
no longer relies on per-setting environment overrides. Local focused suite:
40 passed, including direct Ansible/Vault and shared group-var path resolution.

2026-10-31 human-readable defaults: all 12 lab assertions passed with a site name,
device-role slug and device-type model replacing numeric fixture IDs. Focused
suite: 41 passed, including exact matching, ambiguous/missing names and config
loading for unrelated commands. Existing device assignments remain unchanged.
