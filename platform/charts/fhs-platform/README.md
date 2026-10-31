# FHS platform

One Helm release installs NetBox, PostgreSQL, Valkey, Prometheus, Telegraf,
Grafana, Elasticsearch/Kibana, apt-cacher-ng, persistent devpi, a Squid Git proxy
and the installation home. Dependencies and
dashboards are bundled. NetBox plugins install automatically; no image build
is required.

Run from the repository root. The installation uses release `mid-cbf-hw`,
namespace `hw-management` and prefix `/mid-cbf-hw`.

```bash
# Edit hostnames, certificate Secret names and service types.
vi platform/values-provisioning.yaml
# Install or upgrade the platform with the provisioning endpoints enabled.
helm upgrade --install mid-cbf-hw platform/charts/fhs-platform \
  --namespace hw-management --create-namespace \
  -f platform/values-provisioning.yaml \
  --wait --wait-for-jobs --timeout 20m
```

Storage class and capacity overrides live in `aptCacher.persistence`,
`devpi.persistence` and the application settings in [values.yaml](values.yaml).
Create the DNS records and TLS Secrets before deploying; see
[HTTPS setup](CONFIGURATION.md#https-endpoints).
Defaults are in [values.yaml](values.yaml).
Use the same release, namespace, credentials and volumes for upgrades. Back up
databases before schema/plugin changes; Helm rollback does not restore data.

Open <https://rmdskadevdu011.mda.ca/mid-cbf-hw/>. Application paths below it are
`netbox/`, `grafana/` and `mid-cbf-kibana/`. Change the host with `global.hostname`.

| Default resource | Name |
|---|---|
| NetBox Deployment/Service | `fhs-netbox` |
| Grafana Deployment/Service | `fhs-grafana` |
| Landing Deployment/Service | `mid-cbf-hw-hw-landing` |
| Kibana Deployment/Service | `mid-cbf-hw-elastic-kibana` |
| Ingress | `mid-cbf-hw-web` |

`fhs-platform-credentials` holds login keys `password` (NetBox/admin),
`admin-password` (Grafana/admin) and `elastic-password` (Kibana/elastic).

```bash
kubectl -n hw-management get pods,pvc,ingress
```

[Discovery, home and logging settings](CONFIGURATION.md).
[Optional prebuilt NetBox image](netbox-image/README.md).
