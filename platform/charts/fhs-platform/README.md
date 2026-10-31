# FHS platform

One Helm release installs NetBox, PostgreSQL, Valkey, Prometheus, Telegraf,
Grafana, Elasticsearch/Kibana, apt-cacher-ng, persistent devpi, a Squid Git proxy
and the installation home. Dependencies and
dashboards are bundled. NetBox plugins install automatically; no image build
is required.

Run from the repository root. The installation uses release `mid-cbf-hw`,
namespace `hw-management` and prefix `/mid-cbf-hw`.

```bash
# Review the existing platform hostname and LoadBalancer service types.
vi platform/values-provisioning.yaml
# Install/upgrade, wait for readiness, then export credentials and endpoints.
platform/deploy.sh
```

Storage class and capacity overrides live in `aptCacher.persistence`,
`devpi.persistence` and the application settings in [values.yaml](values.yaml).
The development overrides use HTTP without additional DNS records or TLS Secrets; see
[endpoint settings](CONFIGURATION.md#development-http-endpoints).
Defaults are in [values.yaml](values.yaml).
Use the same release, namespace, credentials and volumes for upgrades. Back up
databases before schema/plugin changes; Helm rollback does not restore data.

Open <http://rmdskadevdu011.mda.ca/mid-cbf-hw/>. Application paths below it are
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

## Get passwords

Run on the cluster management machine. These commands print the passwords for
the deployed platform:

```bash
# NetBox login: admin
kubectl -n hw-management get secret fhs-platform-credentials \
  -o jsonpath='{.data.password}' | base64 --decode
printf '\n'

# Grafana login: admin
kubectl -n hw-management get secret fhs-platform-credentials \
  -o jsonpath='{.data.admin-password}' | base64 --decode
printf '\n'

# Elasticsearch / Kibana login: elastic
kubectl -n hw-management get secret fhs-platform-credentials \
  -o jsonpath='{.data.elastic-password}' | base64 --decode
printf '\n'

# Filebeat publishing user: filebeat_writer
kubectl -n hw-management get secret fhs-platform-credentials \
  -o jsonpath='{.data.filebeat-password}' | base64 --decode
printf '\n'
```

## Export Ansible settings

The deployment helper runs this automatically after Helm succeeds. To export
again without deploying, run on the cluster management machine:

```bash
python3 platform/charts/export-platform.py
```

The script checks service DNS/connectivity, registers the platform's NetBox API
token and writes these local files beside the Helm scripts:

```text
platform/charts/platform-export/platform-secrets.yml
platform/charts/platform-export/platform-endpoints.yml
```

It uses the current kubectl context, release `mid-cbf-hw` and namespace
`hw-management`. Select another context with `--context <CONTEXT>`. It reuses the
chart's existing credentials; it does not rotate them or copy files elsewhere.
The secrets file contains the NetBox token, Filebeat publishing credentials and
Elasticsearch administrator credentials for setup. Keep it private.

Copy the files yourself to the Ansible host's resource directory. Inside the
provisioning container, their destinations are:

```text
/provision/files.d/credentials/platform-secrets.yml
/provision/files.d/platform-endpoints.yml
```

Then, inside that container:

```bash
chmod 600 /provision/files.d/credentials/platform-secrets.yml
ansible-vault encrypt /provision/files.d/credentials/platform-secrets.yml
python3 -m pip install -r playbooks/netbox/requirements.txt
# Copy netbox_url from platform-endpoints.yml into api_endpoint in this file:
vi inventory/dev_env/netbox-inv.yml
ansible-inventory -i inventory/dev_env/netbox-inv.yml --graph
```

On the Ansible host, from its repository checkout, check the file using the
host-side resource path (the Compose default is shown):

```bash
python3 platform/charts/export-platform.py \
  --check-endpoints /shared/midcbf_provision_files.d/platform-endpoints.yml
```

This check needs Python 3, not kubectl. APT/Git checks confirm DNS/TCP
reachability; other services also receive an unauthenticated HTTP HEAD request.
These checks do not establish API privileges or successful package downloads.
If a name does not resolve from the Ansible host, resolve that site's service
DNS access before provisioning. No DNS records are created by the exporter.

Machine-specific paths remain in inventory. Optional environment variables
`FHS_PLATFORM_SECRETS_FILE` and `FHS_PLATFORM_ENDPOINTS_FILE` override the two
controller file locations for inventory and playbooks. The existing Vault
password-file configuration decrypts the secrets automatically.
