# Controller packaging evidence — 2026-10-26

Source paths/releases come from
[update_repositories.yml](../../../playbooks/development/update_repositories.yml).
Fetched public Git repositories, selected tag `0.0.3` (no credentials):

- FSP: `4419cbc0c50a9aefc94a410933044cfaf83ba81c`,
  `ska-telescope/ska-mid-cbf/host-software/ska-mid-cbf-fhs-fsp-grpc-controller`.
- VCC: `d4ca8d088e8dfe22a96ad622203472283e3e6503`,
  `ska-telescope/ska-mid-cbf/host-software/ska-mid-cbf-fhs-vcc-grpc-controller`.

Both include `pyproject.toml` and Poetry lock format 2.1. Local inspection copies:
`/tmp/fhs-role-cleanup-fsp` and `/tmp/fhs-role-cleanup-vcc`.

Observed comparison with current role templates:

- Console scripts are `ska-mid-cbf-fhs-{fsp,vcc}-grpc-controller`, targeting each
  package's `server:run`. Both real CLIs require plural `--devices`, `--regions`,
  `--cards`; the role templates currently pass singular flags. They support
  `--host`, `--port`, `--log`, `--bitstream_pkg_path`, `--emulation_mode`.
- FSP dependencies include grpcio/grpcio-tools `^1.81.0`, protobuf `^6.33.0`,
  pydantic-settings, structlog and click. VCC instead uses grpcio `^1.62.0`,
  protobuf `^4.25.0`, jsonref and pinned certifi/idna/markupsafe/urllib3.
  Do not unify these dependency sets casually.
- Current FSP template removes dev/docs groups and replaces all package sources
  with `pip_index_url`; VCC retains dev but removes docs and also replaces
  sources. Neither override has a matching checked-in deployment lock. Current
  deployment regenerates unconstrained locks every time, then reports unchanged.
- Real FSP declares SKA Nexus, GitLab FHS common and public PyPI; VCC declares
  public PyPI. pip configuration alone does not select Poetry's declared sources.
- VCC imports `py_driver_wrap` at module load in its driver instantiator, including
  the emulation startup import path. Its pyproject does not declare this package.
  Correct bitstream/SDK driver paths remain a real prerequisite, even for emulation.

Recommendation (not implemented here): fix dependency packaging in the controller
and driver repositories so wheels declare/import their runtime dependencies and
carry reviewed locks/index metadata. Do not modify those repositories in this
scope. Until then, keep minimal documented deployment overrides with approved
matching locks; preserve FSP/VCC differences. Never regenerate locks at deployment.

Still pending stage 4: inspect real bitstream archive layouts, resolve actual
NetBox tag shapes, implement controller selection/service transition, unprivileged
runtime/PATH/PYTHONPATH configuration, merged Poetry responsibility, focused
stand-in service/rerun scenario. These source findings are not service validation.

## Stage 4 source findings and implementation

The NetBox plugin used by the existing inventory (`netbox.netbox.nb_inventory`,
`extract_tags`, locally installed at `/tmp/fhs-alignment-collections`) converts
API tag dictionaries into **string slugs**. Role selection supports these and
explicit dictionary fixtures; no live inventory or credentials were queried.
The inventory's API-side tag shape must not be assumed to be the hostvar shape.

Public selected bitstream repositories fetched read-only (without submodules):

- FSP 0.1.0: `ed41565199a4130b07419a8afc499b24a0d557e4`,
  `ska-telescope/ska-mid-cbf/infra/ska-mid-cbf-fsp-corr-bitstreams`.
  Actual tree: `raw/ska-mid-cbf-agilex-fsp-corr`, not the old VCC path.
- VCC 1.2.0: `b573e9dfc4e51c4f8ce9cfbdd4153b7b712f7aed`,
  `ska-telescope/ska-mid-cbf/infra/ska-mid-cbf-bitstreams`.
  Actual tree: `raw/ska-mid-cbf-agilex-vcc`.

Both contain `drivers/fpga_driver_common/driver/py_driver_wrap.py`. Its top-level
imports are standard-library ctypes/fcntl/etc.; source inspection does **not**
establish that an additional proprietary SDK is needed merely to import this
file. This corrects the earlier broad SDK-path assumption. Real VFIO access,
dynamic drivers, application startup and hardware remain untested. Local source
copies are `/tmp/fhs-stage4-bitstream-{fsp,vcc}`; private downloaded archive
contents were not available and are not claimed verified. The downloader's
GitLab web-archive convention supplies the release-named top-level directory.

Pinned Poetry 2.2.1 `check --lock` on each original controller 0.0.3 pair exits 0.
Both report existing SPDX/PEP-621/console-script deprecation warnings. Preserve
these original pairs and distinct dependency versions by default. Retire the
role's replacement pyproject templates; no copy of a lock with changed sources
is guessed or silently regenerated. Alternate-index deployment explicitly accepts
an approved matching pyproject/lock pair. This is an artifact prerequisite when
original Poetry indexes are unsuitable; `pip_index_url` alone only configures
the Poetry tool installation. No real alternate-index pair is shipped/claimed
validated. A small approved fixture pair tests that override path separately.

Recommendation remains to fix package metadata, driver dependencies and approved
locks in controller/driver source repositories through their owners. No upstream
repository modifications/pushes were made. Runtime service uses actual plural
CLI flags and console scripts, controller-specific driver paths, unprivileged
account/group and restart-on-failure. No SDK or FPGA correctness claim follows.
