# Isolated Bifrost API smoke

A disposable Ironic API check using the actual Bifrost base image. Empty inventory; no conductor, DHCP, PXE, image build or provisioning cycle. The API binds only container loopback, using a temporary SQLite database. Docker uses an internal bridge without published ports. The container is non-root, read-only, unprivileged and drops all capabilities; only the empty inventory is mounted.

Assessed source: official development `87dc794742b8d32e1b7e3346c1423162c7e19e41`, `bifrost-infra/{docker-compose.yml,Dockerfile,TESTING.md}` and `scripts/deploy-bifrost-container.sh`. The source deployment uses host networking, privilege, host devices, real inventory and DHCP; do not run that launcher in this lab. This fixture pins the source Dockerfile's base image by the digest resolved on dragonvm. Custom image packages and the complete deployment are not replicated.

On dragonvm, from this directory (Docker Compose v2):

```sh
python3 -m unittest discover -s tests -v
docker compose -f compose.json config --quiet
docker compose -f compose.json pull
./smoke.sh
```

`smoke.sh` starts its disposable project, validates the Bifrost playbooks and empty inventory, creates a database, serves `/v1/nodes`, verifies HTTP 200 and an empty node list, then removes the container and bridge even on failure. Startup never pulls or builds implicitly. The explicit `pull` downloads the pinned image. Do not keep work in this disposable project. `docker compose -f compose.json up -d --pull never` starts only the idle preparation shell; the smoke entry point starts the API separately. Existing clusters and host services are untouched.

2026-10-21 validation on dragonvm: pinned image pull, actual Bifrost filesystem check and saved `smoke.sh` passed; API returned HTTP 200 with empty nodes. SQLite schema initialized successfully. Two safety tests passed locally and remotely; Compose accepted the configuration. The one-worker API logged a spawn-to-fork fallback warning; the API request and cleanup succeeded. A separate cached-image probe verified Docker's internal bridge, no ports/privilege, dropped capabilities, read-only root, UID 65534 and no default route. Probe resources were removed. Temporary inputs: `/tmp/fhs-bifrost-prep-evidence` on dragonvm.

KVM capability check passed: API version 12, `KVM_CREATE_VM` and `KVM_CREATE_VCPU`; descriptors closed without booting a guest. QEMU is installed. This proves nested KVM exposes those operations, not guest boot or provisioning. Before a full disposable VM test, budget memory alongside Kubernetes, pin custom image/download inputs, and separately implement/review the isolated VM/BMC network. No physical hardware behavior is established by this smoke check.
