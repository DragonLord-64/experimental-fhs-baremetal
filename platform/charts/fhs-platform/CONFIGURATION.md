# Platform settings

Set site overrides in `platform/values-provisioning.yaml`; install/upgrade commands are in the
[README](README.md). Full defaults: [values.yaml](values.yaml).

## Access

`global.hostname`, `scheme`, `urlPrefix`, `ingressClassName` and `tlsSecretName`
configure the shared ingress. The home and application links use the same prefix.
Supply the TLS Secret separately if needed.

## Home page

`landing.enabled` enables the home at the prefix root. NetBox, Grafana and Kibana
links come from deployment settings. Websites are checked every 60 seconds;
the page shows reachability and the last check time. Application logins stay
with each application.

Use `landing.introduction` for brief Markdown, or add
`--set-file landing.introduction=./introduction.md` to the Helm command.
Headings, paragraphs, bold and HTTP(S) links are supported; HTML is escaped.

```yaml
landing:
  links:
    - name: Documentation
      url: https://docs.example/installation
    - name: Jira
      url: https://jira.example/projects/HW
    - name: Confluence
      url: https://wiki.example/installation
```

`landing.timeoutSeconds` defaults to 4; `staleSeconds` to 150.
Optional `extraChecks` entries take `id`, `name`, public `url`, internal
`endpoint` and `expected` HTTP codes. Up to five are supported.
`netbox.enabled`, `grafana.enabled` and `logging.kibana.enabled` control the
managed links and application routes. Disabling Kibana also requires
`logging.filebeatSetup.enabled=false`.

## NetBox

Inventory 2.7.1, Prometheus SD 2.2.0 and Topology Views 5.0.0 install automatically
on NetBox 4.7.0. Topology Views is under `netbox/plugins/netbox_topology_views/`.
It displays recorded cables; uploaded custom icons use ephemeral pod storage.

Inventory synchronizes serials/tags and supports the `faulty` asset status.
Change-log retention is `netbox.changelogRetention` (default 90 days).

## Prometheus discovery

1. Create a read-only legacy NetBox API token with device-view access. Store it
   in Secret `fhs-netbox-discovery`, key `token`, in the installation namespace.
2. Add device multi-select field `prometheus_exporters` with choices `node` and
   `fhs`. Select installed exporters on active devices with primary IPv4s.
3. Enable `global.discovery.enabled` and remove migrated node/FHS targets from
   the static scrape list, retaining unrelated jobs.

Refresh defaults to 30s. `selector: tags` uses `node-exporter` / `fhs-exporter`
tags instead. Exporters must already be installed on the selected hosts.

## Logging

Run [Ansible Filebeat setup](../../../roles/filebeat/README.md) to load index
management from the same package installed on servers. The Helm setup job is
disabled by default; enable it only when its additional assets are wanted.

`logging.filebeatSetup.enabled` runs Filebeat setup on upgrades: templates,
system ingest pipelines, ILM and the `fhs-filebeat` Kibana data view. Retention
defaults to 30d for a new policy. Existing policy and data-view settings remain.
It installs no collector. `logging.filebeat.enabled` creates the limited
`filebeat_writer` account used by server shippers. Run setup before shipping logs.

## APT cache

`aptCacher.enabled` installs `mid-cbf-hw-apt-cacher` on TCP 3142 with a
20Gi persistent cache (`bds1`). Override `aptCacher.persistence.storageClass`
and `size` for the site. Logs are ephemeral under `/var/log/apt-cacher-ng`.
The retained cache claim survives Helm uninstall; remove it explicitly to
discard cached packages.

The service defaults to ClusterIP. Set `aptCacher.service.type: NodePort`
and optionally `nodePort`, or use `LoadBalancer`, for provisioning clients
outside Kubernetes. Restrict external access to the provisioning network.
Use the reachable service address in `/etc/apt/apt.conf.d/01proxy`:

```text
Acquire::http::Proxy "http://CACHE_HOST:3142";
Acquire::https::Proxy "http://CACHE_HOST:3142";
```

For NodePort use the assigned node port instead of 3142. HTTPS CONNECT is
allowed only for archive.ubuntu.com, security.ubuntu.com, deb.debian.org,
download.docker.com, rmdlinuxrepo.mda.ca and pkgs.k8s.io on port 443.
HTTPS tunnels are passed through; HTTP package downloads are cached.
To change the allowed HTTPS destinations, edit `PassThroughPattern` in
`templates/apt-cacher-config.yaml`, then run the Helm upgrade command.

## Python and Git proxies

`devpi.enabled` installs `mid-cbf-hw-devpi` on 3141, backed by a retained 10Gi
claim at `/var/devpi`. Override `devpi.persistence.storageClass`/`size` for the
site. One replica and Recreate protect its SQLite state. Startup needs up to
1Gi for secret hashing in the pinned image. Back up the claim before upgrades;
there is no automated database migration. Initialization creates an unknown
random root password; this is a public PyPI cache, with no usable admin login
or private uploads. Existing claims keep their existing account policy.

`gitProxy.enabled` installs `mid-cbf-hw-git-proxy` on 3128. Squid allows GET,
POST and HEAD to `gitProxy.allowedDomains`, plus CONNECT to those domains only
on 443. Defaults are `gitlab.com` and `git-collab.nrc-cnrc.gc.ca`; add required
redirect/archive hosts deliberately. A leading dot allows subdomains. No disk
cache or TLS interception is used. Git still verifies origin certificates.

The chart defaults to ClusterIP. `platform/values-provisioning.yaml` sets APT,
devpi and Git services to LoadBalancer for the separate provisioning machines.
Your deployment's LoadBalancer DNS integration can map service names to external
addresses. Use the configured service names and check resolution from the provisioning host and targets.

Set these values in `inventory/dev_env/group_vars/device_roles_fpga-host-server/distribution.yml`:

```yaml
apt_cache_url: http://mid-cbf-hw-apt-cacher.hw-management.svc.cluster.local:3142
pip_index_url: http://mid-cbf-hw-devpi.hw-management.svc.cluster.local:3141/root/pypi/+simple/
pip_allow_insecure_http: true
pip_trusted_hosts: [mid-cbf-hw-devpi.hw-management.svc.cluster.local]
pip_trusted_hosts: []
git_proxy_url: http://mid-cbf-hw-git-proxy.hw-management.svc.cluster.local:3128
```

Restrict proxy access to approved provisioning clients. APT retains Signed-By
verification over the HTTP cache. Git uses an HTTP proxy with a verified HTTPS
connection through it to the origin; no TLS interception is needed. Do not embed
credentials in system-wide URLs. The pip HTTP exception is limited to the
configured cache hostname; do not disable upstream HTTPS verification.

## Development HTTP endpoints

`platform/values-provisioning.yaml` uses HTTP for the existing platform hostname
and disables dedicated devpi/Elasticsearch ingresses. It exposes these services
through LoadBalancer:

| Service DNS name | Port | Client setting |
|---|---|---|
| `mid-cbf-hw-apt-cacher.hw-management.svc.cluster.local` | 3142 | `apt_cache_url` |
| `mid-cbf-hw-devpi.hw-management.svc.cluster.local` | 3141 | `pip_index_url` |
| `mid-cbf-hw-git-proxy.hw-management.svc.cluster.local` | 3128 | `git_proxy_url` |
| `mid-cbf-hw-elastic.hw-management.svc.cluster.local` | 9200 | `filebeat_elasticsearch_hosts` |

Verify these names resolve and are reachable from the provisioning host and
managed servers using the site's existing service DNS integration. Kubernetes
alone does not make cluster service DNS available outside the cluster.

Set Elasticsearch in
`inventory/dev_env/group_vars/device_roles_fpga-host-server/monitoring.yml`:

```yaml
filebeat_elasticsearch_hosts:
  - http://mid-cbf-hw-elastic.hw-management.svc.cluster.local:9200
```

Set NetBox in `inventory/dev_env/netbox-inv.yml` and in the protected import/export
credentials file:

```yaml
# inventory/dev_env/netbox-inv.yml
api_endpoint: http://rmdskadevdu011.mda.ca/mid-cbf-hw/netbox/
validate_certs: true
```

```yaml
# /provision/files.d/credentials/mid-cbf-hw-netbox.yml
netbox_url: http://rmdskadevdu011.mda.ca/mid-cbf-hw/netbox/
netbox_token: "<NetBox API token>"
netbox_validate_certs: true
```

Certificate validation settings remain enabled for a future HTTPS URL; they do
not encrypt HTTP. No internal CA installation or TLS Secret is needed for HTTP.
Keep credential files Vault-encrypted and restrict service access to the trusted
development LAN. NetBox tokens and Elasticsearch credentials cross that LAN
unencrypted. HTTP is an accepted development tradeoff, not a production policy.
Elasticsearch authentication and APT signature verification remain enabled.

HTTPS may be enabled later using a TLS proxy or an approved ingress, matching
certificates and client CA trust. The optional chart ingress settings and
`setup_platform_ca` role remain available; they are not required by this setup.

Images are pinned by digest in values.yaml: prebuilt
[jonasal/devpi-server](https://github.com/JonasAlfredsson/docker-devpi) (6.20.3)
and [Canonical Squid](https://hub.docker.com/r/ubuntu/squid) (24.04 channel,
actual packaged Squid 6.13). No image build or startup package download is
required. The registry tag is descriptive; the digest selects the tested image.
