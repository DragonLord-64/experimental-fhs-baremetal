# Inventory plugin trial

Disposable synthetic inventory, separate from `fhs-test`. NetBox `4.7.0` and
[NetBox Inventory](https://github.com/ArnesSI/netbox-inventory) `2.7.1` (MIT).
Base, PostgreSQL and Valkey images are pinned by digest. No real inventory is imported.

Copy this folder to `~/fhs-netbox-inventory-trial-20261023` on dragonvm, then run there:

```sh
python3 prepare.py              # private .env and credentials.json, created once
docker compose build
docker compose up -d
# Wait for "Initialisation is done" in docker compose logs netbox.
python3 bootstrap.py            # private API token; records change-log retention
python3 acceptance.py           # real REST tests; fixtures retained for inspection
```

HTTP binds only `127.0.0.1:18087`; use an SSH tunnel. Login is in
`credentials.json`; never paste it into documentation or screenshots.
The web process uses one worker, capped at 2.5 GiB; PostgreSQL/Valkey at 384/128 MiB.
The trial has no background worker and is not a production deployment.

Tests cover a DAC serial, quarantine shelf and custom `Faulty / quarantine` status;
and an FPGA spare assigned to a real NetBox module, then retained after that module
is deleted. Serial and asset tag synchronize while installed. Both keep real NetBox
change-log rows. The DAC uses manual standalone asset status/location transitions;
native `Cable` linking and automatic cable-removal detection are outside this trial.
Faulty status is searchable, not an automatic restriction on reuse.

`acceptance.json` contains sanitized results and fixture URLs. Change-log retention
is recorded there; this is not a permanent history guarantee. On the trial instance,
NetBox's default is 90 days; the background maintenance worker is absent here.

Stop this trial with `docker compose stop` from its folder. Its named volumes and
fixtures remain. Leave the separate minikube cluster and paused pipelines untouched.

Actual synthetic trial: [assets](screenshots/assets-overview.jpg),
[faulty DAC](screenshots/dac-quarantined.jpg), and
[FPGA removal history](screenshots/fpga-module-removed.jpg).
