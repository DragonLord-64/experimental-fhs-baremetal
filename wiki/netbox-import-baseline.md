# Working NetBox import baseline

The user confirmed: **“the import worked.”** This is a successful physical-hardware
run reported by the user, following the FPGA DAC correction. It is distinct from
the earlier synthetic lab checks; no complete run log or per-host counts were
supplied with this confirmation.

Working code: [`b966fb7`](https://github.com/DragonLord-64/experimental-fhs-baremetal/commit/b966fb7),
tag `baselines/netbox-import-working-20261025`. This identifies the private
experimental source; it does not assert an official upstream deployment SHA.
Run commands and stage tags remain in the [importer README](../playbooks/netbox/README.md).

## Locked decisions

- FRU **Product Serial** (SYS number) identifies the server, apart from explicit
  overrides. Chassis Serial is a property; Board Serial identifies the motherboard.
- FRU Product Part Number supplies the server model. Product Name holds the
  manufacturing date. Linux supplies hostname, OS, interfaces and addresses.
- Board, DIMM, NVMe, NIC, FPGA and pluggable observations populate their own
  components. Missing manufacturer uses `NA`; missing optional data must not
  prevent creation of a server with a usable serial.
- Server-info supplies supplemental role, placement and PDU outlet assignments.
  Role is unassigned unless explicitly supplied. PDU discovery and switch VLAN
  import are out of scope.
- Connections use LLDP and FPGA DAC serial matching. FS `QDD-400G-PC01`
  complementary `BASE-1`/`BASE-2` ends match only with matching vendor/part and
  one FPGA connector plus one switch connector. Preserve both complete serials.
  Exact serial matches and explicit endpoint mappings retain precedence.
- An absent observation never authorizes deletion. Observed identity corrections
  update installed records; occupied cable/IP/MAC conflicts remain protected.
- Stages are `servers`, `modules`, `interfaces`, `ips`, `cables`. No tags or `apply`
  runs all stages. An unhandled failure stops that host; other hosts continue.
  Some optional collectors rescue failures. Independent recovery across every
  stage is **not implemented**.

## Evidence and limits

Raw hardware references are in official `development2` at
[`a41dc8f`](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/tree/a41dc8f/playbooks/netbox/raw-reference).
The corrected sys1392 capture has working LLDP and BittWare output; retain
sys1391 as additional hardware evidence. Raw captures contain real identifiers;
do not copy them into public fixtures or documentation.

The run screenshots exposed OOB assignment before IP creation and a role POST
HTTP 500. Commit `8902803` moved OOB assignment into the IP stage and serialized
shared prerequisite creation; the server-side cause of that HTTP 500 was not
confirmed. Commit `4d2807b` corrected product identity and manufacture-date
mapping; `b966fb7` added paired DAC serial matching.

The earlier full reference review identified additional component detail and
switch MAC/IP improvements. Those are **not all implemented** by this baseline.
A working run does not establish complete capture of every optional field.

## Change discipline

Preserve this baseline. Make one scoped change at a time, explain the expected
behavior, and let the user validate on hardware. Do not bundle stage refactors,
log cleanup or wider collector redesign into a fix. The user requested no further
test harness work for this iteration. Proposed skip-output cleanup and independent
stage recovery remain future work, not part of the accepted baseline.
