# Inventory alignment checks

Pinned NetBox `4.7.0` + MIT Inventory `2.7.1`; shared image/configuration in the
[portable chart](../../../platform/charts/fhs-platform/README.md). The chart uses
the public base image and installs the pinned plugin at startup; the legacy lab
[deployment entrypoint](../deploy.sh) uses the optional prebuilt image.
Never use the default Kubernetes context (`monitoring`) for these tests.

```bash
python3 -m unittest discover -s ops/platform/inventory-alignment -p 'test_*.py' -v
python3 -m unittest discover -s ops/platform/umbrella -p 'test_*.py' -v
```

After the parent activates the delivered chart on existing cluster `fhs-test`,
run native importer acceptance with an isolated synthetic namespace/database:

```bash
python3 ops/platform/inventory-alignment/acceptance.py \
  --credentials /private/alignment.json --report /tmp/alignment-acceptance.json
```

The mode-0600 input JSON contains `url` (NetBox base, including prefix) and
`token`. Requirements: `ansible` and `ansible-playbook` on PATH, PyYAML for the
harness and `requests` in the module interpreter;
set `FHS_ANSIBLE_PYTHON` if it differs from the Python running acceptance.
The harness uses native Ansible module packaging/CLI and real REST, never fake
Ansible imports. It retains uniquely named `SYN-ALIGN-*` fixtures for inspection.
It covers chassis serial/hostname identity, FPGA/NIC/component/Nexus asset
repeat/replacement/removal, uncabled interface ID retention, journals, real
change logs and manual standalone DAC quarantine without inventing a peer.
It also executes actual compare tasks in check mode with existing IP/MAC owners
before a chassis rename, and tests real cabled replacement refusal.
No physical server or switch is contacted.

The full umbrella render remains a separate check. A resource-limited scoped
NetBox + backing-service activation proves those components only; do not report
monitoring/logging capacity or a full-stack deployment from that run. Record
runtime plugin configuration, image, migrations/readiness, API status, prefixed
static HTTP paths, media affinity and history retention with the report.

The routing/task-flow tests require real Ansible and loopback permission; without
Ansible they explicitly skip. No skip substitutes for runtime acceptance.

See [screen/baseline](HANDOFF.md), [official source review](UPSTREAM.md) and
[actual validation](VALIDATION.md).

## Optional IPMI FRU

`test_fru.py` covers distinct identities, source precedence, placeholders/date
models, missing/failed/partial records, selected/multiple FRUs and asset
preservation. Its native task checks use fake local commands and synthetic REST.
`fixtures/fru.txt` follows a user-supplied FRU photo's field structure; serials,
product part number and extra metadata are synthetic. Manufacturer and board
model names retain the distinct system/board vendors. The private image is not
stored here.

Run the actual identity/compare/apply tasks against the isolated chart NetBox:

```bash
python3 ops/platform/inventory-alignment/acceptance_fru.py \
  --credentials /private/alignment.json --report /tmp/fru-acceptance.json
```

Use the same dependencies/private URL-token JSON as `acceptance.py`, plus the
NetBox collection and `pynetbox` from the importer requirements. Only fake local
IPMI/DMI commands are executed. The run retains unique `SYN-FRU-*` objects and a
sanitized last-task log beside the report. It does not establish physical BMC
access or firmware behavior.

`test_startup_plugin.py` checks all three consumers, non-root package volumes,
pinned hash enforcement, offline prebuilt detection and installation failure.
The launcher regression also verifies static collection before serving.
