# Manage FHS gRPC

Retired from `site.yml`. The installer remains as historical reference; use
[the tagged certificate cleanup](../../docs/src/playbooks/certificate-update.md)
to stop/remove existing FSP/VCC controllers and their environments.

Installs one controller selected by NetBox `grpc-fsp` or `grpc-vcc` tag.
Neither tag skips installation; both fail before filesystem/account changes.
The NetBox inventory plugin emits string slugs; dictionary tags with `slug` are
also accepted. Switching tags stops/disables and removes the previous role-owned
`fsp-grpc.service` or `vcc-grpc.service`, then starts the selected controller.
These two unit names are reserved for this role.

Poetry installation belongs to this role; the standalone manage_poetry role is
retired. Python with venv support and the approved archives from
`playbooks/development/update_repositories.yml`
are prerequisites. Default controller releases are 0.0.3, Poetry is pinned to
2.2.1. `manage_grpc_archive_dir` is controller-side. Archives must contain the
named release directory. No grpcurl/proto installation or polling is performed.

## Configuration

See `defaults/main.yml`. `manage_grpc_controllers` holds each
controller's release, bitstream, `devices`, `regions`, `cards` (equal-length lists),
`port`, `bitstream_pkg_path` and `python_paths`. When overriding this dictionary,
supply the complete selected entry, including `pyproject` and `lock` (empty uses
the release files). Existing single-card `manage_grpc_card`,
`manage_grpc_device_address`, `manage_grpc_device_region` and `manage_grpc_port`
feed the default entries. `manage_grpc_host` defaults to loopback; configure an
approved bind address explicitly for remote clients. No authentication/TLS is
added by this role; do not expose the endpoint beyond its approved network.

Verified release source layouts:

- FSP 0.1.0: `raw/ska-mid-cbf-agilex-fsp-corr`.
- VCC 1.2.0: `raw/ska-mid-cbf-agilex-vcc`.

Each uses its own `drivers` and `drivers/fpga_driver_common/driver` on PYTHONPATH.
PATH contains executables only. Existing approved archives must include these
files; repository inspection does not prove the contents of a private archive.

## Dependencies and runtime

By default the original release pyproject and lock are preserved, including
FSP/VCC dependency differences and Poetry sources. `pip_index_url` selects the
index for installing Poetry itself; it does **not** replace Poetry project
sources. To use an alternate project index, supply **both** controller-side
`pyproject` and `lock` paths in the selected entry. Prepare/review that matched
pair ahead of deployment; preserve selected-release dependencies and scripts,
change only required source metadata. `poetry check --lock` must pass. No lock
is generated on the server. Never embed index credentials in these files.

Installation uses `poetry install --only main` and a project-local .venv. A
success fingerprint is written only after installation; changed release content,
pyproject/lock, Python path or Poetry version, or a missing console entrypoint,
causes installation. An unchanged rerun neither installs nor restarts. Unit or
selected bitstream changes restart the service; stopped services are started.

Root owns installation code and environments. Runtime uses `fhs-grpc` with the
shared `bittware` group/GID 666, preserving supplementary groups. The service has
`Restart=on-failure`. Supply appropriate VFIO device permissions for real use;
root execution is not the workaround. Real controller dependency packaging should
be fixed upstream to declare driver imports and provide reviewed deployable
locks/index metadata; those repositories are outside this change.

Focused tests cover real Poetry installation of stand-in packages, fresh-user
permissions, selection, reruns and controller switching with a service-manager
stand-in. Real systemd startup/recovery, selected-release dependency installation,
SDK/driver imports and FPGA behavior remain unvalidated. Emulation is enabled by
default; it does not establish hardware correctness.
