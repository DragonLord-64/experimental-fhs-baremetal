# FHS platform

NetBox, Prometheus, Telegraf, Grafana and Elasticsearch/Kibana in one Helm release.
Copy this whole folder, including `charts/` and `dashboards/`.
Requires Helm 3, Kubernetes >=1.25, `nginx` ingress and `nfss1` / `bds1` storage.
NetBox installs Inventory automatically; pods need PyPI access.

## Install / upgrade

Set `KUBE_CONTEXT` to the intended cluster and keep the existing private
`site-values.yaml`. Back up databases and Secrets before upgrading.
Run from the directory containing `fhs-platform/`:

```bash
helm upgrade --install mid-cbf-hw ./fhs-platform \
  --kube-context "$KUBE_CONTEXT" --namespace hw-management --create-namespace \
  -f site-values.yaml --set-string global.urlPrefix=/mid-cbf-hw \
  --wait --wait-for-jobs --timeout 20m
```

Use the same command for updates; retain the release, namespace and volumes.
Helm rollback does not reverse database migrations.

## Verify / access

```bash
helm status mid-cbf-hw --kube-context "$KUBE_CONTEXT" -n hw-management
kubectl --context "$KUBE_CONTEXT" -n hw-management get pods,pvc,ingress
```

- [NetBox](https://rmdskadevdu011.mda.ca/mid-cbf-hw/netbox/)
- [Grafana](https://rmdskadevdu011.mda.ca/mid-cbf-hw/grafana/)
- [Kibana](https://rmdskadevdu011.mda.ca/mid-cbf-hw/mid-cbf-kibana/)

NetBox/Grafana login: `admin`; Kibana: `elastic`. Passwords are retained in
`fhs-platform-credentials`. Site hostname and paths come from the chart values.
