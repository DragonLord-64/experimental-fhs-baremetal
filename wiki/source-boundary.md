# Source and lab boundary

Shared source paths stay aligned with official `ska-mid-cbf-fhs-baremetal`.
Compared against official `development2` at `0658e93` on 2026-10-24. This is a
copy boundary, not a claim that every private change has been accepted upstream.

For the 2026-10-30 update against official `2638d5b`, use the
[current transfer prerequisites](../ops/security-provisioning/TRANSFER.md).
The old host snapshot is not copied over current NetBox inventory.

| Copy/sync as source | Keep experimental |
|---|---|
| `platform/` — values, bundled charts/dashboard assets, NetBox image recipe | `ops/` — lab services, orchestration, emulators, acceptance tests, captures |
| `playbooks/`, `roles/`, `inventory/`, `bifrost-infra/` | `wiki/` — plans, decisions, source/evidence notes |
| `docs/src/` and the existing docs build configuration | `examples/` — standalone synthetic demos |
| `scripts/`, `testing/` and reviewed upstream root build/config files | `AGENTS.md`, `INDEX.md` and private workflow instructions |

Copy whole source folders, including internal module utilities, chart dependencies
and image build recipes. Review the diff before transfer; supply private
credentials separately. Never sync experimental Git history into the official
repository or push official upstream from this checkout. Root files are selected
individually; do not copy the whole private repository over the official tree.

## Moved lab material

| Before | Current location |
|---|---|
| `platform/grafana_dashboards/` | `ops/dashboards/` |
| `platform/example_output/` | `ops/telemetry/captures/` |
| `docs/test-environment-plan.md` | `wiki/test-environment-plan.md` |
| private `scripts/test-manage-users.sh` and expanded Molecule scenario | `ops/role-tests/manage_users/` |
| private `tests/molecule/` dependencies | `ops/role-tests/dependencies/` |
| lab guide formerly under `docs/src/guide/platform.md` | `ops/platform/guide.md`; shared guide now describes portable deployment |

The official three-file `manage_users` Molecule scenario and official all-role
script remain at their original paths, byte-identical to the reviewed official
revision. They are separate legacy source, not the validated custom lab runner.
The legacy source's earlier missing-role/collection-path issues remain recorded;
use the custom lab command for the validated role test. Production role behavior
is unchanged. Other upstream docs/tests, including `testing/`, were not moved.

The chart keeps compressed runtime dashboards; it never imports the development
generator during installation. The [NetBox image recipe](../platform/charts/fhs-platform/netbox-image/README.md)
and its build context are inside the copied chart under `platform/`. No shared
runtime script or symlink reaches into `ops/`, `wiki/` or `examples/`.

## Checks

These checks apply when changing source boundaries or the corresponding runtime
inputs. Wiki-only edits need local content/link checks, not these suites.

```sh
python3 -m unittest discover -s ops/source-boundary -v
python3 -m unittest discover -s ops/dashboards/tests -v
python3 -m unittest discover -s ops/platform/umbrella -v
```

The boundary check copies `platform/` into an isolated directory, renders the
chart, decodes all six dashboards and exercises the image build context with a
fake Docker command. The relocated role runner is exercised with stubbed CLIs;
this verifies paths/cleanup wiring, not another real container run. Historical
live role evidence is retained beside its moved scenario. Captures/reference
hashes and official-file provenance are in
[the relocation manifest](../ops/source-boundary/PROVENANCE.json).
