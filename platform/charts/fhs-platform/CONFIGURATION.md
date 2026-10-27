# Platform settings

Set site overrides in `site-values.yaml`; install/upgrade commands are in the
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

Filebeat setup is temporarily disabled by default because its image pull is
unavailable. Re-enable with `logging.filebeatSetup.enabled=true` when ready.

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
The five overrides are in `templates/apt-cacher-config.yaml`; other settings
use the image's packaged apt-cacher-ng defaults. The pinned
[container source](https://github.com/mbentley/docker-apt-cacher-ng) supplies
the package; its broad CONNECT override is replaced by this chart.

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

Both default to ClusterIP. Like APT, each supports `service.type` and optional
`service.nodePort`. Set reachable addresses in inventory, rather than copying
cluster DNS names to servers outside Kubernetes:

```yaml
apt_cache_url: http://<apt-proxy-host>:3142
pip_index_url: http://<python-index-host>:3141/root/pypi/+simple/
git_proxy_url: http://<git-proxy-host>:3128
```

These are unauthenticated internal endpoints, with no TLS listeners. Restrict
reachability to approved provisioning clients; do not publish them on the
Internet. For pip on an untrusted network, provide approved HTTPS termination
and CA trust instead of `pip_trusted_hosts`. The latter bypasses certificate
verification. APT keeps Signed-By verification; HTTP cache transport does not
replace package signatures. Do not embed credentials in system-wide URLs.

Images are pinned by digest in values.yaml: prebuilt
[jonasal/devpi-server](https://github.com/JonasAlfredsson/docker-devpi) (6.20.3)
and [Canonical Squid](https://hub.docker.com/r/ubuntu/squid) (24.04 channel,
actual packaged Squid 6.13). No image build or startup package download is
required. The registry tag is descriptive; the digest selects the tested image.
