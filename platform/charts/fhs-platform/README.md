# FHS platform

Copy this whole folder, including `charts/` and `dashboards/`, into your repo.
Requires Helm 3, Kubernetes >=1.25, existing ingress class `nginx` and storage
classes `nfss1` / `bds1`. Dependencies and six dashboards are included.

One release installs NetBox, PostgreSQL, Valkey, Prometheus, Telegraf, Grafana
and Elasticsearch/Kibana. Chart dependencies are bundled. NetBox uses the public
upstream image; startup installs pinned Inventory `2.7.1` automatically for web,
worker and housekeeping. No custom image build or registry is required.

Pods need HTTPS access to PyPI at startup. Installation verifies the wheel hash
and runs as UID 1000 in per-pod writable volumes. Plugin installation is repeated
when a pod is replaced; database records remain in PostgreSQL. A matching
[prebuilt image](netbox-image/README.md) skips the download for offline use.

## Install / upgrade

On your hardware control node, select the intended context and an unused
namespace and URL prefix. Check spare capacity, existing routes and storage first.

```bash
KUBE_CONTEXT="$(kubectl config current-context)"
helm upgrade --install fhs-platform ./fhs-platform \
  --kube-context "$KUBE_CONTEXT" \
  --namespace mid-cbf-monitoring-test --create-namespace \
  --wait --wait-for-jobs --timeout 20m \
  --set-string global.urlPrefix=/test
```

The existing user deployment profile is release `mid-cbf-hw`, namespace
`hw-management`, prefix `/mid-cbf-hw`. Preserve its private extra values:

```bash
helm upgrade --install mid-cbf-hw ./fhs-platform \
  --kube-context "$KUBE_CONTEXT" --namespace hw-management \
  -f site-values.yaml --set-string global.urlPrefix=/mid-cbf-hw \
  --wait --wait-for-jobs --timeout 20m
```

Use that profile only for the intended existing deployment. The candidate
example above remains separate. Back up NetBox PostgreSQL before plugin
activation or migrations; keep the existing release credentials and data.

Run the same command after updating this folder or adding `-f site-values.yaml`.
Keep the same release name, namespace, credentials and volumes on upgrades.
When updating from the earlier local-image version, remove any private
`netbox.image` overrides pointing to `fhs/netbox-inventory`; use the public image
settings shipped in this folder. Do not reset unrelated site values.

If startup fails, inspect the NetBox pod Events and the
`install-inventory-plugin` init-container log. `ImagePullBackOff` is an image
retrieval failure; a package-download failure appears in that init-container log.

- `--namespace`: use an unused namespace for a candidate; preserve the existing one for an upgrade.
- `global.urlPrefix`: `/test`, `/review/team-a`, or another unused prefix.
- `global.hostname`: defaults to `rmdskadevdu011.mda.ca`.
- `global.ingressClassName`, `global.scheme`, `global.tlsSecretName`: optional overrides.
- Empty prefix uses the original app paths: check collisions before cutover.

Default browser addresses:

- <https://rmdskadevdu011.mda.ca/test/netbox/>
- <https://rmdskadevdu011.mda.ca/test/grafana/>
- <https://rmdskadevdu011.mda.ca/test/mid-cbf-kibana/>

HTTPS uses the existing front door's host certificate. If setting
`global.tlsSecretName`, supply that TLS Secret in the candidate namespace.
The chart creates no certificates. Dashboards appear in **FHS infrastructure**;
their links automatically use the configured prefix.

NetBox's pinned image launcher serves static assets at `/static` by default.
The chart adjusts that launcher route to `<global.urlPrefix>/netbox/static`,
matching NetBox's base path. Initialization and the other launcher settings are
preserved; no separate values override is needed.

NetBox web, worker and housekeeping share a `ReadWriteOnce` media PVC. Following
the [upstream storage guidance](https://github.com/netbox-community/netbox-chart/blob/main/charts/netbox/README.md#persistent-storage-pitfalls),
required pod affinity keeps these consumers on one node, selected by chart,
release and component labels in the same namespace. No node name is fixed.

For the existing `hw-management` deployment with the temporary web node selector,
first complete the Helm upgrade with these affinity values, then remove that pin:

```bash
kubectl --context "$KUBE_CONTEXT" patch deployment fhs-netbox -n hw-management \
  --type=merge -p '{"spec":{"template":{"spec":{"nodeSelector":{"kubernetes.io/hostname":null}}}}}'
kubectl --context "$KUBE_CONTEXT" -n hw-management rollout status deployment/fhs-netbox
kubectl --context "$KUBE_CONTEXT" -n hw-management get pods -o wide
```

Helm may retain the manual selector because it was absent from both release
manifests. Confirm the media consumers share a node after the rollout.

## Login / verify

NetBox and Grafana use `admin`; Kibana uses `elastic`. First install generates
`fhs-platform-credentials`; upgrades preserve it. Read passwords locally:

```bash
kubectl --context "$KUBE_CONTEXT" -n mid-cbf-monitoring-test get secret \
  fhs-platform-credentials -o jsonpath='{.data.admin-password}' | base64 --decode
# Grafana: admin-password; NetBox: password; Kibana: elastic-password.
kubectl --context "$KUBE_CONTEXT" -n mid-cbf-monitoring-test get pods,pvc,ingress
```

Verify login, assets, redirects and dashboard navigation. Source node/FHS scrape
targets are in `values.yaml`; missing metric labels stay unknown. Existing
switch/PDU pushes and Filebeat destinations stay unchanged: the new Telegraf
and Elasticsearch need an explicit telemetry cutover. No mock data is installed.

## Data / scope

Fresh database/cache state is the default. Existing PostgreSQL-server and
operator-managed Secret settings are described beside the fields in `values.yaml`.
Use only a separate copied database and login role for a parallel candidate.
Back up databases and Secrets before upgrading; Helm rollback cannot undo schema
migrations. Credentials and PVCs are retained; do not delete the namespace to stop it.

The chart adds its own namespaced resources and Ingress. It installs no controller,
cluster RBAC, StorageClass, explicit PV, LoadBalancer, host mounts or privileged pods.
Workloads still consume shared capacity, PVCs allocate storage/PVs, ingress loads
new routes, and scrapes add load. Offline checks cannot prove zero cluster impact.
For dry-runs use `--dry-run=server --hide-secret`; plain renders can expose credentials.

## Inventory lifecycle

`netbox_inventory` is enabled with serial/tag synchronization and the extra
`faulty` (Faulty / quarantine, red) asset status. Native importers retain removed
physical assets and journal replacement/removal on the parent device. History
follows `netbox.changelogRetention` (default 90 days), so export/retain evidence
outside NetBox for longer retention. Check plugin activation and then validate selected importer operations against
a backed-up test inventory before using them on hardware.
