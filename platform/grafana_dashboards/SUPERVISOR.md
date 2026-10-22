# Supervisor continuation

Keep the paused controller, checkpoints and all unrelated work intact.
Do not resume NetBox/Bifrost or logging. Preserve Grafana 13.2.3 and its data.

Supply `GRAFANA_URL`, `GRAFANA_USER` and `GRAFANA_PASSWORD` privately.

```bash
timeout --signal=TERM --kill-after=10 s 600 s /home/dragon-lord/fhs-docs-tools/bin/python \
  platform/grafana_dashboards/live_validate.py --visual-only --import-owned \
  --output /tmp/fhs-grafana-visual
```

This imports six owned UIDs using bounded ownership discovery, foreign-folder
rejection and optimistic version checks. It never changes credentials, a
source dashboard title or an unrelated dashboard. Same-origin cookie browser
requests continue without injected credentials or response buffering.

Inspect all six actual captures and lower rack, FHS PSU, switch hardware/LLDP
and interface LLDP sections. NoData is acceptable; login/loading/error screens
are not rendering success. Current visual acceptance includes the nine 42 U
racks,648 mesh cells and 128 switch interface slots. Parent hardware health,
optic readings and VLAN allowance remain Unknown where no observations exist.

The full query scenario gate retains earlier strict sensor-coverage assertions;
current native scrape filtering prevents claiming all healthy FHS components.
Run meaningful selected queries independently for the visual milestone. Native
switch-to-interface click validation is implemented; complete rack/mesh/peer
click and title-rename acceptance require independent browser review.
