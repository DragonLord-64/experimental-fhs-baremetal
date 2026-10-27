# JSON transfer — 2026-10-26

[CLI and usage](../../../playbooks/netbox/README.md#portable-inventory-json).
Controller acceptance remains `python3 ops/agent-pipeline/checks.py`; the worker
did not run it. Additional checks below exercise runtime behavior it does not
cover. No deployments, DELETE requests, commits, pushes or host power operations.

- `python3 ops/platform/inventory-alignment/test_transfer.py`: three tests passed.
  Sanitized in-code source/destination fixture uses different IDs, a switch
  management IP/MAC, two PDU outlets, dual server PSU cables and a network cable.
  Checks portable relationships, literal nested JSON, repeat/no duplicates,
  preview without writes, unrelated-record retention, missing/ambiguous references,
  occupied IP/cable preservation, omitted/empty fields, foreign pagination URL
  refusal, prohibited DELETE and exclusive mode-0600 files.
- Whole-file and inline Vault credential checks passed using Ansible's installed
  facilities, a temporary password file and synthetic URL/token. Interpreter
  environment: `PYTHONPATH=/tmp/fhs-credentials-runtime/lib/python3.14/site-packages`,
  `PATH=/tmp/fhs-alignment-python/bin:$PATH`,
  `ANSIBLE_LOCAL_TEMP=/tmp/fhs-transfer-ansible`. The first attempt used an older
  incomplete Ansible copy and failed before decryption; it was not a CLI pass.
- Inspected existing services/pods with
  `ssh -F /home/dragonlord/.ssh/config dragonvm 'minikube -p fhs-test kubectl -- --context=fhs-test get services,pods -A'`.
  Existing inventory-alignment NetBox, PostgreSQL and Valkey were running.
  Inspected installed serializers and authenticated OPTIONS, including writable
  relations, generated fields and the cable profile validation edge.
- Native entry point: `transfer_native.py --script /tmp/.../netbox_transfer.py
  --vars /tmp/.../vars.yml --report /tmp/.../report.json`, executed via
  `minikube -p fhs-test kubectl -- --context=fhs-test -n fhs-inventory-alignment exec -i fhs-netbox-6fdf459f7f-vn8n6 -- /opt/netbox/venv/bin/python -`.
  A temporary bootstrap copied these two scripts and created protected vars from
  the existing mounted lab secret; it removed those vars afterward. Final run:
  **9 assertions passed, 20 objects, no fixture issues**. Private report/input and
  partial report remain inside the pod at `/tmp/fhs-transfer-1lnqzcu7/`.
  The check uses real detail serializers, OPTIONS and POST/PATCH requests, and
  retains separate source/destination synthetic scopes in the same database.
  It verifies different destination IDs, primary IP/interface resolution, nested
  JSON custom fields, two PSU cables plus a network cable, unchanged source and
  a rerun without writes. It is not a two-server migration or hardware test.
- Actual CLI export against the final source switch: **61 objects, exit 2,
  mode 0600**. Private artifacts: `cli-export.json` and `cli-export-report.json`
  in that same pod directory. It reported Inventory component assignment IDs,
  duplicate MAC identity from an earlier failed fixture and unsupported plugins.
  The component assignment now uses its content type and portable reference;
  this final small adapter change has local coverage only, not a second native
  export run. Export deliberately reports issues encountered during the initial
  supported-endpoint scan, including records outside a later device selection.

Earlier native attempts exposed fixture slug collisions, cable `profile: null`
rejected by its own writable serializer, MAC case normalization and repeated
empty custom-field patches. These failed attempts are not passes. Corrections
were followed by the fresh successful fixture above. Earlier `SYN-XFER-*`
records and private pod artifacts remain for inspection; nothing was deleted.

## Limits

Inventory plugin assets/types/groups, roles, suppliers, purchases, deliveries and
all audit objects are explicitly unsupported, as are other plugin objects.
Installed plugin/version differences and unavailable destination fields produce
partial reports. Generated connectivity/counts/history are not writable inventory.
Unsupported relationship targets and object custom-field defaults are reported.
Literal JSON may itself contain application-specific IDs; its meaning cannot be
rewritten automatically. Rack/location/module/template paths are implemented but
not exercised by this native fixture. Whole-instance all-field compatibility,
production migration and rollback are not established. API permissions must
expose OPTIONS and all selected dependencies; no permission bypass is attempted.
