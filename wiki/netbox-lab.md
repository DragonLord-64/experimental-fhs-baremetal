# NetBox provisioning lab

Implementation in progress, 2026-10-22. [Commands and ownership](../ops/netbox-lab/README.md), [nonsecret fixture policy](../ops/netbox-lab/fixture.json).

## Mapping

The private archived inventory was inspected locally with mode `0600`. Recognized fields: interfaces, MAC/primary MAC, primary IPv4, OOB IP, tags and custom fields. No raw records, credentials, addresses or names were copied into this checkout. The archive illustrates intended data shape; it does not establish correctness.

- Derive 132 FHS and 51 switches from the read-only canonical dashboard contract: 24 VCC / 27 FSP units and 648 mesh links. Retain canonical identity in `custom_fields.fhs_lab`; prefix synthetic NetBox names with `lab-nb-`.
- One synthetic rack per unit; synthetic FHS/switch device types and roles. Canonical host and switch ports are native interfaces. Primary management and separate OOB interfaces use unique synthetic MAC/IP assignments. Mesh port names are retained; cabling is not yet populated.
- Logical records carry `lab-logical`; three extra records carry `lab-provisioning`, fixed UUIDv5 identities and fake hardware properties. No record implies a reachable SSH or BMC endpoint. No reachable target is registered yet.
- Documentation networks only: canonical `192.0.2.0/24`, provisioning `198.51.100.0/24`, OOB `203.0.113.0/24`. All records are synthetic; no device connections occur during bootstrap/export.
- NetBox owns existing facts after bootstrap. Git owns bootstrap identity/presence and defaults only. Deliberate field changes are preserved. Retiring identities or repairing interrupted creation is explicit work.

Unverified assumption: these synthetic shapes cover future role inputs. Real hardware properties and complete guest provisioning remain outside this test. The existing production Bifrost exporter and its simulated-hardware guard are unchanged; the lab path deliberately requires fake hardware.

## Observed checks

- Prior supervisor seed evidence (`.pipeline-bridge/seed-1.log`, `seed-2.log`): 186 devices (183 logical, three provisioning), 2,196 interfaces, 636 MACs, 372 IPs and 51 racks. Unchanged rerun created zero objects in every category and passed authenticated API/UI checks. These are existing execution logs; this continuation did not reseed.
- Twenty-five offline contracts pass: ownership/idempotence/operator edits, native export facts, filtering, pagination, endpoint guards, diagnostic privacy, null custom-field semantics, actual pinned Ansible inventory JSON marker decoding, private atomic output and stale invalidation including connection failure. Fixed API diagnostics identify devices/interfaces/IP addresses and transport failures without URLs or record values. Native validation now makes one paginated interface query scoped by selected device IDs; the regression checks the query count and still rejects changed interface names/tags. Two existing provisioning isolation tests pass.
- Supervised retries v5/v6 passed authenticated API/UI and plugin invocation but failed field validation. v7 failed parsing; v8 reached validation and reported `ansible_host` type mismatch. The installed core 2.20 inventory encoder wraps untrusted strings; its actual encoder now has a regression test. The consumer decodes only that exact marker for comparison and omits null custom fields as the plugin does. Explicit IPv4 composition and strict non-null field checks remain. Retry v9 passed authenticated readiness and plugin invocation but failed a native-fact API GET. Numeric HTTP-status diagnostics are now implemented; `netbox-read-only-api-status-diagnostics-v10` is requested, not yet executed.
- Actual pinned Bifrost source/fake-driver inspection passed previously (`consumer-v2-0.log`). Loader execution, fake API enrollment/readback/cleanup, live source-of-truth mutation and reachable-target assertions remain unverified. No reachable target is registered. Logical device addresses must never be used for host access.

Bridge logs are local sanitized evidence, excluded from Git. Supervisor requests require matching operation responses; a queued request does not prove execution. The controller owns independent review after implementation.

Saved pod evidence (`.pipeline-bridge/netbox-pod-after.json`) records OOMKilled exit 137 at `2026-10-22T07:47:20Z`, four restarts and a 1,536 MiB / two CPU limit. This is historical evidence, not current readiness. Request `netbox-bulk-native-read-and-serving-inspection-v11` asks for read-only serving/resource measurements before and after one plugin retry; no reseed, serving change or resource increase is authorized by that request.

Implementation continuation: installed collection `3.21.0` batches filtered related-object requests with `limit=0`, default URI budget 4,000, and concurrent lookup tables. Candidate URI budget is now 512 to reduce individual interface response size. Native interface and assigned-IP comparisons each use one scoped paginated query; missing, stale and moved IP assignments fail offline regression checks. Supervisor request `netbox-bounded-plugin-read-v12` requests capacity review before one read-only retry. The matching v11 response held inventory execution; no serving/resource adjustment or reseed was made.

Matching v12 supervisor response: `hold_live_actions_capacity_assessment`. It prohibits new live consumer load and test containers until the supervisor releases the hold. No v12 plugin execution or Bifrost/target test occurred. Offline checks remain 25 lab tests plus two provisioning isolation tests; Compose validation and whitespace checks pass.
