# Source map

- Initial upstream: `https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal.git`, development commit `656983382383e869d3b1ff8484f14cfe05e7b832`.
- [Environment plan](test-environment-plan.md): user discussion on 2026-10-21 plus local read-only inspection; includes history import limitations.
- [Platform README](../platform/README.md): imported deployment instructions for Prometheus, Telegraf, Elasticsearch, and Kibana.
- [Telemetry samples](../ops/telemetry/captures): existing node, FHS, and switch samples; suitability for replay remains unverified.
- [GitLab CI](../.gitlab-ci.yml): existing lint and documentation configuration; no role-test execution observed in this file.
- [Lab role runner](../ops/role-tests/manage_users/run.sh): invokes the validated [manage_users container scenario](../ops/role-tests/manage_users/molecule/default/README.md). The official all-role script remains separate legacy source with its earlier collection-path limitation; other role scenarios remain unvalidated.
- DragonMind `AGENTS.md` and `README.md`: organizational inspiration for concise linked notes, provenance, and distinct plans and events; its unrelated automation is not adopted here.

## Workspace provenance

The original checkout `/home/dragonlord/ska-mid-cbf-fhs-baremetal` was fast-forwarded to official development `87dc794` for configuration assessment. The private working checkout was `/home/dragonlord/experimental-fhs-baremetal`, remote `DragonLord-64/experimental-fhs-baremetal`, branch `development`. Paths describe that inspection, not every isolated worker checkout. The experimental upstream push URL was disabled with `/dev/null`; never push to official SKA repositories.

The snapshot-history limitation and preserved full history are recorded in the [environment plan](test-environment-plan.md). Transfer accepted changes through reviewed patches or cherry-picks; do not merge unrelated histories casually. Earlier controller/platform milestones are in the append-only [log](LOG.md); current behavior belongs to the linked operations pages, not a conversation handoff.

## Official development2 review — 2026-10-24

Reviewed official `development2` at `0658e93b7fa0ebbcdbcb85afcce99b1cbbc45bcd` against experimental `eee2d6d`; no history merge. See [reviewed transfer and older gaps](../ops/platform/inventory-alignment/UPSTREAM.md). The portable chart, platform moves and archives were already represented. Carried the missing placeholder-MAC exclusions and the existing `mid-cbf-hw` deployment profile into the aligned implementation.

## Copy boundary — 2026-10-24

[Source versus lab layout](source-boundary.md) records the official comparison,
relocated lab generators/captures/test harness and preserved upstream docs/tests.
The custom role runner now lives outside `scripts/` and `roles/`; the official
legacy entrypoints are preserved separately.
