# Platform lab access

Use the [single-release platform chart](../../platform/charts/fhs-platform/README.md)
with reviewed lab overrides. Inspect the existing `fhs-test` cluster before
selecting a namespace/release; always name its context explicitly.

```bash
kubectl --context=fhs-test get services -A
kubectl --context=fhs-test -n <NAMESPACE> port-forward \
  --address 127.0.0.1 svc/<SERVICE> <LOCAL_PORT>:<SERVICE_PORT>
```

Discover the actual service port and application base path before forwarding.
Keep credentials and captures outside Git. See [lab checks](README.md),
[native importers](inventory-alignment/README.md) and
[provisioning/security evidence](../security-provisioning/VALIDATION.md).

The configured monitoring flow is PDU/switch telemetry → Telegraf → Prometheus
→ Grafana, and Filebeat → Elasticsearch → Kibana. Synthetic fixtures do not
establish physical hardware or telemetry behavior.
