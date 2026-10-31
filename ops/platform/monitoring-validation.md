> Historical separate-release lab results. The scripts recorded below were removed; use [current lab checks](README.md).

# Monitoring lab checks

2026-10-22 UTC, dragonvm, `fhs-test` context, `fhs-platform` namespace.

- Official chart indexes confirmed Prometheus 29.35.0 / app v3.15.0, Telegraf 1.8.77 / app 1.40.1 and Grafana 13.2.7 / app 13.2.3. All three rendered successfully with VM values.
- Prometheus, Telegraf, Grafana, Elasticsearch and Kibana reached Ready. Elasticsearch/Kibana use source local chart 0.5.0 and pinned 9.5.5 images.
- `bash ops/platform/monitoring-test.sh` passed: synthetic JSON PDU POST; Telegraf `pdu_power_watts`; Prometheus value query; authenticated Grafana datasource query; Grafana health; authenticated Elasticsearch health; unauthenticated Elasticsearch rejected with 401; Kibana status and authenticated spaces API.
- Each test uses a fresh synthetic `pdu_id`, loopback ephemeral forwarding ports and owned process groups. Cleanup verification found no forwarding descendants after the corrected test.
- The chart's default Telegraf renderer v1 dropped nested regex tag dictionaries. Lab `tplVersion: 2` preserves both source Cisco regex mappings; parsed rendered TOML confirmed two mappings. No Cisco hardware telemetry was tested.
- An initial test started before Elasticsearch listened and failed when that forward exited. The test now waits for all five service rollouts before forwarding.
- An unchanged Helm rerun preserved all five service pod UIDs and restart counts; the Elasticsearch service-user setup Job runs again by release revision. This proves no service rollout for identical values, not byte-identical Helm release state.

```sh
bash ops/platform/monitoring-deploy.sh deploy
bash ops/platform/monitoring-test.sh
```

Run on dragonvm after main orchestration creates the namespace, `fhs-retain` volumes and both credential Secrets. Source values are loaded before lab overlays. Prometheus production scrape targets are replaced; services use ClusterIP. No real targets, LAN listeners or external ingress are configured. Credentials are supplied by the main deploy helper, never values files.

Official indexes: <https://prometheus-community.github.io/helm-charts/index.yaml>, <https://helm.influxdata.com/index.yaml>, <https://grafana-community.github.io/helm-charts/index.yaml>.

Temporary VM evidence: `/tmp/fhs-monitoring-{before,after}.json`, `/tmp/fhs-monitoring-rerun.log`, `/tmp/fhs-monitoring-telegraf-v2.yaml`. These files contain lab metadata/configuration, not Secret values. Hardware telemetry, stop/start recovery and upgrades remain separate checks.
