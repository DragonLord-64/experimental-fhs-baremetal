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

`prune.py` builds an offline exact plan from a scoped collector capture. It requires 23 retained and 160 obsolete logical devices; provisioning fixtures, physical inventory and history cannot be deletion targets. IP/MAC objects are detached and preserved, including their prefixes, VRFs and history. Raw address cascades may authorize only the exact owned disassociation stage; they never authorize deletion. There is no orphan-delete cleanup.

After independent source review, the supervisor can run these scripts **inside the owned lab NetBox pod**, using its existing Django shell. Workers must not run them against a deployment:

```sh
# Metadata only: versions, relation types, nullability and on_delete; no records.
python manage.py shell < /private/reviewed/schema-inspect.py
# Reviewed files inventory.py/prune.py/collector.py must share this module path.
PYTHONPATH=/private/reviewed FHS_PRUNE_IDS=/private/obsolete-ids.json FHS_PRUNE_OUTPUT=/private/scoped.json python manage.py shell < /private/reviewed/collector.py
```

The selected IDs file is a reviewed list of unique obsolete device IDs (maximum 160). The initial collector reads the owned-tag/site population and its dependencies; refreshes read only frozen device IDs plus their current dependencies (all four scope tables are required); it never calls `.delete()`. PostgreSQL read-only repeatable-read, 15-second statement/2-second lock limits, a 60-second query deadline, 1,000-query budget and 12,000-row scope/recursive/effect bounds fail closed. No global table snapshots. Installed ORM compatibility still requires the reviewed metadata/collector execution.

The first installed read-only capture passed the 183/23/160 selection guard but exhausted the unchanged query budget during API serialization (lazy device parent-bay reads); it returned no snapshot and performed no inventory writes. The focused source fix replaces DRF serialization with bounded native ORM `values()` queries: every concrete field, choice value/label, custom fields, forward relation ID, reverse one-to-one ID (including `parent_bay`), many-to-many IDs and ownership tags are captured. Site slugs and assigned-object content types remain explicit. Native IP/MAC values use canonical strings; unsupported values fail rather than disappearing. Tagged-item collector queries join tag/content-type references, and ownership checks reuse captured tags. No per-instance serializer properties run. Query count scales with model relations, not row count; all existing transaction/query/time/row guards remain.

This native capture is a new representation. Do not mix an older API serializer retained baseline with it or strip unknown fields to force equality. Independently establish the same native representation for the original retained evidence, preserving its original identities/defaults; do not replace the baseline with current facts to accept drift. Fresh source review must precede a supervisor rerun. Installed capture, exact destructive-plan review and the separate whole-consumer completion gate remain pending; offline doubles do not establish deployed ORM compatibility.

Build the plan offline from reviewed reduced canonical JSON:

```sh
python3 ops/netbox-lab/prune.py --snapshot /private/scoped.json --topology /private/reduced.json --retained-snapshot /private/original-retained.json --output /private/plan.json --scope-output /private/scope.json
```

`--retained-snapshot` is separately reviewed evidence from the original full population, containing all four scope tables for the 23 retained devices and their interfaces/allocations. Do not generate this baseline from the current capture merely to accept drift. It must include original IDs, serials (including empty serials), ownership and all original stored defaults. The reduced topology supplies original management IPs, chassis MACs and canonical unit identities. Planning checks exact stored facts against this baseline, validates management/BMC assignment chains and full-population BMC MAC/OOB offsets, and fails without repair on differences. Programmatic callers supply the same evidence as `topology['retained_snapshot']`; it is included in the plan's topology hash. Obtaining and independently reviewing this evidence remains a supervisor prerequisite; no live retained baseline is claimed here.

Capture/plan files contain inventory facts: use a private directory and keep them out of Git. Outputs are exclusive-create mode `0600`. Parent independently reviews the exact names, IDs, counts, hashes, collector effects and every operation before deletion. A hash alone does not prove approval.

Supervisor integration calls `apply(api, provider, plan, approved_sha256, checkpoint, batch_size=25)` (valid batch size 1..100). `api.call(path, method, data)` is the serialized supervisor's existing lab adapter. `provider()` returns a **new collector capture** each call: set `FHS_PRUNE_SCOPE` to the generated scope file, select the remaining obsolete device IDs, and use a fresh output filename. Frozen IDs keep detached IPs/MACs and changed-ownership records visible. An empty selected-ID list is accepted only with a scope file, for completed-resume verification. Preserve the same frozen scope for the whole run.

Apply refreshes before/after each batch, validates current collector effects and stable stored facts, and resumes only a matching operation prefix. The plan hashes the full original capture; verification uses `safety_projection()` to exclude serializer presentation, `last_updated` and known assignment-derived summaries/counts. Relation summaries compare by ID. Ownership, names, serials, custom fields/history, IP/VRF, actual MAC values and unknown fields remain checked. Native captures also freeze reverse one-to-one relation metadata. Prefix reconciliation clears only the exact frozen reverse references induced by an approved interface primary-MAC or device primary_ip4/primary_ip6/oob_ip detach; unrelated and unknown reverse fields remain checked. Regenerate captures and obtain exact-plan review when adopting this capture format; do not retrofit an approved capture. Atomic mode-`0600` checkpoints bind the plan hash; fresh evidence resolves lost responses or a stale checkpoint. A failed refresh stops writes. External reference/ownership changes fail closed. Read-only transactions do not lock out concurrent writers between checks: supervisor serialization and a quiescent owned scope remain required. Live apply is not exposed by the offline CLI.

Supervisor metadata in `.pipeline-bridge/native-model-metadata-20261022.json` records NetBox 4.7.0-Docker-5.1.1: Module device/bay are non-null and bay is unique. Offline status cannot free a bay. No unused-module workaround is authorized. Nullable native IP/MAC assignments support retaining detached allocations. Metadata alone does not verify Collector behavior.

Existing `playbooks/development/netbox` edits and importer tests are incidental preserved work for separate integration review; this prune task does not accept or extend them. No live collector, reduced-emulator, prune or consumer acceptance is claimed by offline tests.

All Bifrost work is paused, including inspection and cleanup. Actual native-plugin verification remains behind the supervisor resource gate. Keep the web limit at 1536Mi. No worker profile change is justified without read-only queue evidence; no serving changes are included here.

Detach-first staging preserves the original raw Collector graph in the approved
plan. No prospective graph is synthesized: exact owned IP/MAC assignments may
appear in raw effects only while staging disassociations. Unknown/manual effects,
address tag deletion, external references, modules and history still block. Each
capture binds its effects to the scoped stored facts with `facts_sha256`; older
captures without that binding must be recaptured after source review.

A batch always stops before the first DELETE, even if it has capacity remaining.
A fresh actual native Collector capture after all approved PATCH operations must
show no IP/MAC effects before any deletion. Partial detach, failed capture and
lost responses never bypass this boundary; resume revalidates a matching operation
prefix and current evidence rather than trusting a checkpoint. All allocation
facts except assignment pointers remain frozen, including address, VRF, custom
fields and creation/history metadata. No detached address object is deleted.

Supervisor reports the native read-only collection succeeded on NetBox 4.7.0 /
Django 6.1 within the unchanged bounds; its raw graph includes address cascades.
That report establishes neither deletion safety nor live acceptance. This staged
source needs fresh independent review and supervisor captures; original retained
baseline provenance, exact destructive-plan review and the whole-consumer gate
(including paused Bifrost/reachable-target evidence) remain separate requirements.

Source validation (2026-10-22): 72 lab tests and 2 provisioning isolation tests passed. Native reverse-reference regressions cover bounded detach batches, lost-response checkpoint resume, unchanged reruns and unrelated reverse-field drift. Removing the reconciliation fix reproduces the stale-plan failure after two PATCHes. Installed post-detach capture, original retained-baseline provenance, exact-plan approval and whole-consumer acceptance remain supervisor evidence gates; these offline checks do not satisfy them.

Focused source validation (2026-10-22): 73 lab tests and 2 provisioning isolation tests passed. Independent server storage derives IP reverse one-to-one references from device pointers, without `advance()`. The regression reproduced stale-plan failure before the fix, then passed bounded batches, lost responses after the first/second PATCH, checkpoint resume and unchanged reruns. Unrelated IP reverse-field drift still stops writes. Fresh independent source review remains controller-owned; live evidence and the completion gates above remain pending.
