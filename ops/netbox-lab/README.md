# NetBox lab inventory

VM-only synthetic bootstrap for the persistent `fhs-test` / `fhs-platform` NetBox. Credentials come from its existing Kubernetes Secret in memory; no archive records or production inventory are imported. See [mapping and evidence](../../wiki/netbox-lab.md).

With the pinned lab Python requirements installed, run offline checks from the repository root:

```sh
python3 -m unittest discover -s ops/netbox-lab/tests -v
python3 -m unittest discover -s ops/provisioning/tests -v
```

Live commands require supervisor serialization for this pipeline. No nested SSH. Use the separate pinned lab [Python requirements](requirements.txt) and [NetBox collection](requirements.yml). These match the existing VM toolchain (core `2.20.1`, collection `3.21.0`); the consumer checks both versions before use. Compatibility with the running NetBox is pending the actual plugin check. Original exporter requirements are unchanged. Use a separate runtime when installing, with `ANSIBLE_LOCAL_TEMP` under `/tmp`. Do not execute `inventory/dev_env/netbox-inv.yml`.

```sh
python3 ops/netbox-lab/live.py probe
python3 ops/netbox-lab/live.py seed --topology /home/dragon-lord/fhs-pipeline-inputs/dashboard-contract
# Repeat unchanged: all created counts must be zero.
python3 ops/netbox-lab/live.py seed --topology /home/dragon-lord/fhs-pipeline-inputs/dashboard-contract
python3 ops/netbox-lab/live.py verify --ansible-inventory /path/to/pinned/ansible-inventory
# Parent directory must already exist and be private.
python3 ops/netbox-lab/live.py export --output /private/path/nodes.json
```

`seed` checks authenticated API/UI readiness before any mutation. Bootstrap creates missing objects only: owner tag `fhs-netbox-lab`, site `lab-nb-dragonvm`, names prefixed `lab-nb-`. Namespaced shared models also carry a bootstrap description. Collisions fail; nothing is deleted. Primary IP and MAC pointers are initialized only for newly created devices/interfaces. An interrupted bootstrap can leave incomplete objects; inspect and repair those explicitly, rather than overwrite later operator edits. No reset command is provided.

After bootstrap, edit facts in NetBox. Existing status, tags, addresses, interfaces, MAC pointers and custom fields survive seed reruns. Missing fixture objects are recreated. Removing a seeded identity is therefore an explicit fixture retirement decision; do not use repeated bootstrap as routine reconciliation. A fixture topology change is reviewed before applying.

`verify` calls the actual `netbox.netbox.nb_inventory` plugin. It compares active owned device membership, groups, primary/OOB addresses, interfaces, assigned interface IP records, MAC pointers and non-null custom fields with the API (the plugin omits null custom fields). It makes no host connections. Cache is disabled and inventory parse errors fail. Logical documentation-range addresses are never Ansible targets.

Native interface and IP validation each use one paginated query scoped by selected device IDs, rather than one query per device. The pinned plugin uses `limit=0` for related objects; `max_uri_length: 512` bounds its sequential ID batches instead of serializing every interface in one response. Its lookup tables still fetch concurrently. This reduces response size; it does not prove an OOM is impossible. It includes interfaces with changed ownership tags so those changes are still compared. `runtime-inspect.py` is a supervisor-only read-only probe for serving process counts, numeric worker settings, cgroup memory and pod restart/resource state; it never prints environment values or process command lines. Neither command changes serving configuration or limits.

`export` selects only active owned `lab-provisioning` devices at the lab site. It requires `simulated-hardware`, `fake-hardware`, stable UUIDs, primary/OOB documentation addresses and one enabled owned provisioning port with a unique synthetic MAC. This fake API-only path needs no BMC credential. It invalidates stale output before authentication/readiness and validation and atomically writes JSON with mode `0600`. A private Redfish export remains the separate existing production playbook: its simulated-hardware rejection is unchanged. Never pass this fake fixture to physical enrollment.

`bifrost-runtime.sh inspect` is a supervisor-only bounded source/driver inspection in the pinned image, with one 256 MiB disposable container, internal bridge, no ports/mounts/privilege or conductor. It removes its exact labelled container and network. Loader/API enrollment and a reachable Ansible assertion are still pending actual execution; inspection alone proves neither.

Reduced population source: `topology_fixture()` selects VCCUnit1..4 and FSPUnit1..3 (16 FHS, seven switches, 12 mesh links) from the full canonical snapshot. BMC/OOB offsets remain anchored to all 132 hosts and 51 switches; FSP host identities remain after 24 VCCs. The frozen reduced emulator snapshot is still required before live acceptance. Do not use a renumbered reduced snapshot to seed.

`prune.py` is an offline library, with no live command. `plan(snapshot, topology)` traces exact owned active logical devices, interfaces, IPs and MACs; unowned dependencies, archived candidates and external primary references fail closed. The supervisor must supply all four unfiltered tables and complete deletion-collector evidence covering other NetBox relations. Expected initial reduction is 160 of 183 logical devices; provisioning and reachable fixtures are separate. `apply(api, provider, plan, approved_sha256)` requires the parent's exact reviewed plan hash and fresh whole-table comparisons before and after each write. It resumes only an exact completed prefix. Frozen collector evidence must remain available during retries. Independent review is required before supervisor use; a supplied hash alone is not evidence of approval.

All Bifrost work is paused, including inspection and cleanup. Actual native-plugin verification remains behind the supervisor resource gate. Keep the web limit at 1536Mi. No worker profile change is justified without read-only queue evidence; no serving changes are included here.
