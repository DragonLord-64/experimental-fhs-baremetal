# Source map

Current paths were checked at private development `4a0c5cf` on 2026-10-25.
This is source inspection, not a fresh runtime test. Dated service results and
source revisions remain in the linked validation pages and [log](LOG.md).

| Subject | Source of truth |
|---|---|
| Operating constraints and task scope | [Root instructions](../AGENTS.md), [worker workflow](../ops/AGENTS.md), [pipeline](../ops/agent-pipeline/README.md) |
| Portable platform | [Chart README](../platform/charts/fhs-platform/README.md), [configuration](../platform/charts/fhs-platform/CONFIGURATION.md) |
| Lab deployment and resources | [Kubernetes operations](../ops/kubernetes/README.md), [platform lab](../ops/platform/README.md), [environment evidence](test-environment-plan.md) |
| Device identity and inventory | [Importer source/README](../playbooks/netbox/README.md), [development procedures](../docs/src/playbooks/development.md), [native acceptance](../ops/platform/inventory-alignment/VALIDATION.md) |
| Topology | [Import note and dated acceptance](topology-import.md), [Topology Views check](../ops/platform/topology-views/README.md) |
| Dashboards | [Generators and provenance](../ops/dashboards/README.md), [static demo](../examples/grafana-static-demo/README.md), [telemetry captures](../ops/telemetry/README.md) |
| Logging | [Device role](../roles/filebeat/README.md), [bounded fixture evidence](../ops/platform/logging/validation.md) |
| Role testing | [Validated users scenario](../ops/role-tests/manage_users/molecule/default/README.md), [lab runner](../ops/role-tests/manage_users/run.sh) |
| CI configuration | [GitLab lint/docs](../.gitlab-ci.yml), [private focused-check workflow](../.github/workflows/checks.yml); configuration alone is not execution evidence |

DragonMind's `AGENTS.md` and `README.md` informed the concise linked-note layout;
its unrelated automation was not adopted. FoodReserve task/manager sources are
linked from the pipeline README. No `gh` CLI is needed for local checks or task execution.

## Workspace provenance

Initial upstream: `https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal.git`,
branch `development`, commit `656983382383e869d3b1ff8484f14cfe05e7b832`.
GitHub rejected historical binaries larger than 100 MB, so the private repository
starts from that tracked-tree snapshot without shared initial commit ancestry.
Full history was preserved in the original local checkout and
`/home/dragonlord/experimental-fhs-baremetal-source-history.git`.

The original checkout `/home/dragonlord/ska-mid-cbf-fhs-baremetal` was subsequently
fast-forwarded to official development `87dc794` for configuration assessment.
The private working checkout is `/home/dragonlord/experimental-fhs-baremetal`,
remote `DragonLord-64/experimental-fhs-baremetal`, branch `development`.
Worker checkouts may differ. Official upstream's push URL remains `/dev/null`;
transfer user-accepted patches or cherry-picks separately. Do not merge unrelated
histories or push experimental changes to official SKA repositories.

## Source inspection — 2026-10-22

The earlier read-only inspection used a temporary bare clone at published
`f0603c6136d613d6717dad6af5ea8da57520494e`; the working tree was then at `455023d`.
That was a historical inspection, not the current checkout state. It covered the
static demo introduced at `08a399b`, the platform consolidation and the NetBox/POAP
path promotion. Demo correction `62422f1` was later published with NetBox trial
work at `53aabaf`. The checkout synchronized to `eee2d6d` on 2026-10-24 with local
edits preserved. The old untracked emulator candidate and session handoffs were
kept separately; they do not override integrated source or prove current runtime.

## Official development2 review — 2026-10-24

Reviewed official `development2` at `0658e93b7fa0ebbcdbcb85afcce99b1cbbc45bcd`
against experimental `eee2d6d`; no history merge. The
[reviewed transfer and older gaps](../ops/platform/inventory-alignment/UPSTREAM.md)
record the missing placeholder-MAC exclusions and `mid-cbf-hw` profile carried
into alignment. The chart README was later restored byte-for-byte from official
`7b0a306`, as requested; its hash is retained in the boundary manifest.

## Copy boundary — 2026-10-24

[Source versus lab layout](source-boundary.md) records relocated generators,
captures and the custom role harness. Official docs/tests retain their paths;
legacy Molecule entrypoints remain separate from the validated users scenario.
The [manifest](../ops/source-boundary/PROVENANCE.json) preserves source hashes.
Topology import subsequently references official `development2` `dc08629`; see
[its source contract and limits](topology-import.md).
