# Platform deployment and access

`platform/` contains imported configuration from official development `87dc794`, following the upstream `monitoring/` rename. The retained `monitoring/` snapshot is historical. Imported values contain original storage, endpoints and scrape targets; they are not validated dragonvm overrides.

## Monitoring flow

```{mermaid}
flowchart TD
    P[PDU JSON] -->|HTTP /pdu| T[Telegraf]
    S[Switch telemetry] -->|gRPC MDT| T
    T -->|metrics scrape| M[Prometheus]
    E[FHS and node exporters] -->|metrics scrape| M
    M -->|queries| G[Grafana]
    F[Filebeat] -->|logs| L[Elasticsearch]
    L -->|queries| K[Kibana]
```

This is the configured infrastructure flow. The dragonvm check injects synthetic PDU JSON and verifies Telegraf, Prometheus and Grafana queries. It also checks authenticated Elasticsearch and Kibana APIs. It does not validate Cisco telemetry, FHS exporter behavior or Filebeat delivery from physical servers.

## Deployment workflow

1. For the original cluster, review `platform/README.md`, its values and the local `platform/charts/elasticsearch-kibana` chart. Supply private credentials separately. Do not apply those values unchanged to the VM.
2. For the private dragonvm lab, use `ops/platform/deploy.sh`. It loads imported values before `ops/platform/dragonvm/` and `ops/platform/monitoring-values/` overlays, pins images/charts, replaces production scrape targets and uses ClusterIP services in context `fhs-test`, namespace `fhs-platform`.
3. The lab entry point performs readiness and functional checks. Read `ops/platform/VALIDATION.md` and `ops/platform/monitoring-validation.md` for dated results and initial failures. Do not run deployment or lifecycle checks merely to validate documentation.

```bash
# Operational lab commands, from the repository root on dragonvm:
./ops/platform/deploy.sh
./ops/platform/deploy.sh test
```

These commands change or contact the lab. Prerequisites, retained storage and recovery limits are in `ops/platform/README.md`. All seven releases were observed deployed; NetBox object retention passed PostgreSQL pod replacement and a full cluster cycle. This does not establish backups, HA or physical behavior.

## Access

Use an explicit context and loopback forwarding. Discover the service and its port first; keep each forward in its own terminal.

```bash
kubectl --context=fhs-test -n fhs-platform get services
kubectl --context=fhs-test -n fhs-platform port-forward --address 127.0.0.1 svc/<SERVICE> <LOCAL_PORT>:<SERVICE_PORT>
```

Use the service's configured base path (`/netbox/` for NetBox, `/mid-cbf-kibana` for Kibana). Authentication comes from the lab Secrets; do not paste decoded credentials into documentation or captures. Grafana's Prometheus datasource is configured by the lab values. See the imported `platform/grafana.yaml` and the lab overlays before changing dashboards.

Mesh views represent infrastructure connectivity and health. A VCC unit has one FHS and one switch; an FSP unit has four FHSs and one switch. Keep identities and switch interfaces at both ends of each link; see `wiki/unit-topology.md`. No application or observation behavior is implied.

## Separate validation layers

| Layer | Observed boundary |
|---|---|
| Persistent dragonvm platform | NetBox persistence and monitoring API/query checks; dated evidence under `ops/platform/`. |
| Restricted Bifrost smoke | Actual pinned image, empty Ironic API and KVM creation operations; no guest boot, conductor, DHCP or PXE. See `ops/provisioning/README.md`. |
| Lightweight emulators | Synthetic fixtures exercise selected paths; no scale or protocol equivalence is established. |
| Physical hardware | Separate validation required for FPGA, NIC, Cisco, PDU and provisioning behavior. |

The experimental controller under `ops/agent-pipeline/` orchestrates documentation/code stages. It is separate from the persistent lab and from provisioning services.

## Source and evidence

- [Imported platform procedure](https://github.com/DragonLord-64/experimental-fhs-baremetal/blob/development/platform/README.md)
- [Lab deployment and access prerequisites](https://github.com/DragonLord-64/experimental-fhs-baremetal/blob/development/ops/platform/README.md)
- [Observed platform validation](https://github.com/DragonLord-64/experimental-fhs-baremetal/blob/development/ops/platform/VALIDATION.md)
- [Restricted Bifrost fixture](https://github.com/DragonLord-64/experimental-fhs-baremetal/blob/development/ops/provisioning/README.md)
