# Modular platform lab

Run on dragonvm from the repository root:

```sh
./ops/kubernetes/lifecycle.sh up
./ops/platform/deploy.sh          # independent installs, readiness, functional checks
./ops/platform/deploy.sh test
./ops/platform/deploy.sh deploy --with-bifrost  # also isolated Ironic API smoke
python3 ops/platform/netbox-test.py --lifecycle # object survives full down/up
./ops/kubernetes/lifecycle.sh down
```

Requires Python 3, minikube and Helm (`~/.local/bin/helm`, or `HELM_BIN`). Every operation names context `fhs-test`, namespace `fhs-platform`. Releases: NetBox, PostgreSQL, Valkey, Prometheus, Telegraf, Grafana and the local Elasticsearch/Kibana chart. The optional Bifrost flag runs the separate Docker project and API smoke (no guest provisioning); an absent pinned image gets a bounded 300-second pull. Provisioning stays separate: [Bifrost](../provisioning/README.md).

`platform/` was copied from official development `87dc794`; `netbox.yaml` only drops the `COMPUTED VALUES:` CLI heading. PostgreSQL/Valkey shared files are extracted subtrees of those NetBox computed values. Original `monitoring/` remains untouched. Source image pins, settings and recording rules are reused before `dragonvm/` and `monitoring-values/` overrides. No real inventory was imported.

Upstream versions: NetBox `8.3.67` (NetBox `v4.7.0`), PostgreSQL `18.8.13`, Valkey `6.2.16`, Prometheus `29.35.0`, Telegraf `1.8.77`, Grafana `13.2.7`. NetBox chart version was absent from the source capture; `8.3.67` was selected and fetched from the official [NetBox chart](https://github.com/netbox-community/netbox-chart), OCI digest `sha256:b44ee411c125076547a498162035731a56863c40bf97aa5ba0bc2c09c2a4385a`. Its dependencies are separate releases here. Source blank NetBox image tag is resolved to `v4.7.0` and an amd64 digest; source rolling PostgreSQL/Valkey images are pinned to verified amd64 digests. VM overrides disable ingress, LoadBalancers and production scrape targets, lower resource/storage requests, and replace `nfss1`/`bds1` with `fhs-retain`. Legacy flat NetBox probe paths are removed; chart-generated HTTP paths follow `/netbox/`. Recreate strategy prevents concurrent schema migrations. The pinned image no longer creates the chart's legacy `api_token` automatically; `netbox-bootstrap.sh` creates one named lab validation token from the mounted Secret, inside the pod. It preserves existing tokens and uses the source-compatible v1 API scheme; v2 token rollout is outside this lab change.

Preparation creates fresh lab secrets only if absent; no credentials are printed or stored in Git. Test API objects are disposable. NetBox checks authenticated CRUD and reads the object after PostgreSQL pod recreation; monitoring checks synthetic PDU metrics through Telegraf, Prometheus and Grafana, plus authenticated Elasticsearch/Kibana health.

Storage uses twelve static `Retain` hostPath volumes in `/data/fhs-platform/` inside the minikube node. This avoids the default provisioner's changing identity after restart. Each PV's `8Gi` is nominal scheduling capacity, not a disk quota or reservation; all share the VM disk. Deleted claims leave retained data/PVs for explicit operator recovery; there is no automatic reset/reclaim command. This is a single-node lab without HA or a backup guarantee. `down`/`up` retains objects and data; never delete the minikube profile to stop work.

The fhs-test Docker container was increased from 4 GiB to 6 GiB using `docker update --memory=6g --memory-swap=8g fhs-test`; minikube cannot resize an existing profile itself. `lifecycle.sh up` requests 6 GiB for new profiles. Kubernetes reports host memory rather than the container cgroup limit, so watch actual `docker stats` use. No unrelated container or default context is changed.

Live evidence and initial corrections: [VALIDATION.md](VALIDATION.md).

Bounded one-server logging fixture and reviewed execution commands: [logging/README.md](logging/README.md). Real Filebeat ingest and inspected Kibana Discover proof passed using the explicit filestream fallback; see [evidence and limitations](logging/validation.md).
