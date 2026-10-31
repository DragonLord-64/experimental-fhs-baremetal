> Historical separate-release lab results. The scripts recorded below were removed; use [current lab checks](README.md).

# Platform validation

2026-10-21 Vancouver / 2026-10-22 UTC, dragonvm, context `fhs-test`, namespace `fhs-platform`.

- Checksum-verified Helm `v3.19.0` installed in `~/.local/bin`; system executables unchanged.
- Official NetBox OCI chart `8.3.67` fetched, app `v4.7.0`. PostgreSQL `18.8.13` and Valkey `6.2.16` installed independently; image digests resolved before use. Live PostgreSQL reported `18.6`.
- Final `./ops/platform/deploy.sh deploy --with-bifrost` exited zero after the full cluster cycle, including corrected preparation, all functional checks and actual isolated Ironic API smoke/cleanup. All service pods were Ready; no forwarding descendants or disposable NetBox sites remained. Default context still `monitoring`.
- All seven Helm releases deployed. `./ops/platform/deploy.sh` exited zero, including readiness and functional tests.
- Authenticated NetBox API created/read/deleted a disposable site. The same object remained readable after deleting/recreating the PostgreSQL pod; pod UIDs differed. No database reset was used.
- `python3 ops/platform/netbox-test.py --lifecycle` exited zero: the disposable NetBox object survived full `fhs-test` down/up and was then deleted. Retained PV/PVC objects were reused; no reclaim workaround was needed. This directly checks PostgreSQL data retention, not every application database.
- Monitoring functional checks passed; see [details](monitoring-validation.md). An unchanged monitoring rerun retained all five service pod UIDs and restart counts. The Elasticsearch credential setup Job intentionally runs again by release revision.
- [Bifrost API smoke and KVM checks](../provisioning/README.md) passed using the pinned actual image. Full guest provisioning, custom image build and physical hardware behavior are untested.
- Python compilation and Bash syntax checks passed on dragonvm. Independent review identified preparation retry behavior; permissions helpers now have unique owned names and bounded cleanup.

Initial installation exposed production `global.storageClass: nfss1` taking precedence over the NetBox media override. Only the newly created unbound empty PVC was replaced with `fhs-retain`. An obsolete and current NetBox pod then attempted migrations concurrently; switching the single-instance lab to Recreate removed the obsolete pod, and remaining migrations completed. The final chart/source/image combination requires explicit legacy lab API-token bootstrap; see [README](README.md). A later post-restart DELETE hit a transient HTTP 500 after the persisted-object GET succeeded. The owned site was removed with a prefix-checked ORM operation; deletion now retries only server errors for a bounded 30 attempts (each request has a 15-second timeout, with 2 seconds between retries), while authentication and validation errors fail immediately. Source database connection lifetime remains 300 seconds. Initial failures are not counted as passes.

Temporary VM evidence: `/tmp/fhs-platform-deploy.log`, `/tmp/fhs-platform-lifecycle.log`, `/tmp/fhs-platform-final-retry.log`, plus the monitoring evidence paths. Logs contain lab deployment information; they are not committed captures or durable backups.
