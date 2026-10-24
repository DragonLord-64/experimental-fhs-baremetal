**Monitoring PSI MDA SKA Hardware**  
===================================================  

Imported configuration from official development `87dc794`; these commands target the original cluster, not the private VM lab. Review values, storage, endpoints and credentials before use. NetBox is included in `platform/netbox.yaml`; its image build recipe ships with the chart.
Build the [Inventory image](charts/fhs-platform/netbox-image/README.md) before
installing those values. The canonical values enable Inventory `2.7.1`, serial/tag
synchronization and Faulty / quarantine on NetBox `4.7.0`.

For one Helm install/upgrade, copy the self-contained
[FHS platform chart](charts/fhs-platform/README.md). It automatically installs
Inventory on the public NetBox image, with no custom image registry. It includes
the monitoring/logging services and six runtime dashboards; the legacy separate
release values above use the optional prebuilt image.

**Objective**  
Deploy a complete monitoring stack (Prometheus, Telegraf, Elasticsearch‑Kibana, Filebeat) on a Kubernetes cluster.

---

### 1. Create the Namespace  

```bash
kubectl create namespace mid-cbf-monitoring
```

---

### 2. Generate the Elasticsearch Credentials Secret  

> **Important** – Do not commit generated values to source control. Store them in a secure password manager or an Ansible Vault.

```bash
# Create a temporary directory with permissions 0700
umask 077
creds=$(mktemp -d)

# Generate random passwords and the encryption key
openssl rand -hex 24 > "$creds/elastic-password"
openssl rand -hex 24 > "$creds/kibana-password"
openssl rand -hex 24 > "$creds/filebeat-password"
openssl rand -hex 32 > "$creds/kibana-encryption-key"

# Create the Kubernetes Secret
kubectl -n mid-cbf-monitoring create secret generic elastic-credentials \
  --from-file=elastic-password="$creds/elastic-password" \
  --from-file=kibana-password="$creds/kibana-password" \
  --from-file=filebeat-password="$creds/filebeat-password" \
  --from-file=kibana-encryption-key="$creds/kibana-encryption-key"

# After the `kubectl create secret …` command has run successfully,
# remove the temporary directory that held the clear‑text passwords:

rm -rf "$creds"     # deletes the directory and everything inside it
unset creds          # (optional) clear the shell variable
```

If the secret `elastic-credentials` already exists, add any missing keys rather than recreating it.

#### 2.1 Access credentials.

Use the following command with the correct target parameter to access the kubernetes secret

#### Retrieve service credentials

```bash
# example for filebeat
kubectl -n mid-cbf-monitoring get secret elastic-credentials \
  -o jsonpath="{.data.filebeat-password}" | base64 --decode

# example for kibana
kubectl -n mid-cbf-monitoring get secret elastic-credentials \
  -o jsonpath="{.data.kibana-password}" | base64 --decode
```

---

### 3. Add Helm Repositories (run once)  

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add influxdata          https://helm.influxdata.com
helm repo update
```

---

### 4. Install the Desired Components  

All commands are executed from the repository root.

#### Prometheus  

```bash
helm upgrade --install monitoring-prometheus \
  prometheus-community/prometheus \
  --version 29.35.0 \
  -n mid-cbf-monitoring \
  -f platform/prometheus.yaml
```

#### Telegraf (switch metrics and PDU listener)  

```bash
helm upgrade --install switch-telegraf \
  influxdata/telegraf \
  --version 1.8.77 \
  -n mid-cbf-monitoring \
  -f platform/telegraf.yaml
```

#### Elasticsearch + Kibana (local chart)  

```bash
helm upgrade --install logging ./platform/charts/elasticsearch-kibana \
  -n mid-cbf-monitoring \
  -f platform/elasticsearch.yaml \
  -f platform/kibana.yaml \
  --wait --wait-for-jobs --timeout 10m
```

*To deploy Elasticsearch without Kibana, omit the `kibana.yaml` overlay or set `kibana.enabled=false`.*

---

### 5. Access Kibana  

#### 5.1 Port‑Forward (quick test, no Ingress)  

```bash
kubectl -n mid-cbf-monitoring port-forward svc/logging-elastic-kibana 5601:5601
```

Open a browser at `http://localhost:5601/mid-cbf-kibana` and log in with:

* **Username:** `elastic`  
* **Password:** value stored in `elastic-password` from the secret created in step 2.

#### 5.2 External Access via Ingress (optional)  

Edit `platform/kibana.yaml` before the Helm installation, replacing the placeholders:

```yaml
kibana:
  ingress:
    enabled: true
    className: <INGRESS_CLASS>          # e.g. nginx
    host: <KIBANA_HOSTNAME>            # DNS name that resolves to the ingress controller
    tlsSecretName: <TLS_SECRET_NAME>   # optional, for HTTPS termination
  publicBaseUrl: "https://<KIBANA_HOSTNAME>/mid-cbf-kibana"
```

After Helm completes, verify the Ingress resource:

```bash
kubectl -n mid-cbf-monitoring get ingress
```

No additional path‑rewrite annotations are required; the chart already handles the `/mid-cbf-kibana` base path.

---

### 6. Configure the Telegraf PDU JSON Endpoint  

The chart provisions an HTTP listener on **port 8080** with the path `/pdu`.

Obtain the internal address of the Telegraf service:

```bash
kubectl -n mid-cbf-monitoring get svc switch-telegraf -o jsonpath='{.spec.clusterIP}'
```

Configure each Raritan PDU to send JSON payloads to:

```
http://<TELEGRAF_IP>:8080/pdu
```

Authentication and TLS are not enabled; restrict network access to the trusted private network.

**Test the listener**

```bash
curl -i -X POST \
  -H 'Content-Type: application/json' \
  --data '{"pdu_id":"test","power_watts":123}' \
  http://<TELEGRAF_IP>:8080/pdu
```

A successful request returns HTTP 204. The metric will be visible to Prometheus under `pdu_power_watts`.

---



### 7. Filebeat Configuration on Each Server  

See [filebeat role](../roles/filebeat/README.md)


### 8. Verify the Deployment  

| Verification Item                     | Command / UI                                                                                     |
|--------------------------------------|---------------------------------------------------------------------------------------------------|
| Elasticsearch cluster health          | Use the authenticated command below. |
| Prometheus targets                    | `kubectl -n mid-cbf-monitoring port-forward svc/monitoring-prometheus-server 9090:80` then open `http://localhost:9090/targets` |
| Telegraf PDU metric                   | `curl http://<TELEGRAF_IP>:9273/metrics | grep pdu_power_watts` |
| Filebeat logs in Kibana               | Open Kibana → **Discover** → create a Data View `filebeat-*` and select it                     |
| Kibana Ingress accessibility          | `curl -s -o /dev/null -w "%{http_code}" https://<KIBANA_HOSTNAME>/mid-cbf-kibana/` → Expected `200` |

---

Elasticsearch security is enabled. Use the container's secret-backed password, as in the [chart readiness probe](charts/elasticsearch-kibana/templates/elasticsearch.yaml); do not print it or enable shell tracing:

```bash
kubectl -n mid-cbf-monitoring exec svc/logging-elastic -c elasticsearch -- \
  /bin/bash -ec 'curl --fail --silent --max-time 3 --user "elastic:${ELASTIC_PASSWORD}" "http://127.0.0.1:9200/_cluster/health?wait_for_status=yellow&timeout=1s&pretty"'
```

### 9. Rotating Passwords  

To rotate any credential, update the `elastic-credentials` secret and perform a Helm upgrade of the `logging` release:

```bash
# Delete or edit the existing secret
kubectl -n mid-cbf-monitoring delete secret elastic-credentials   # or `kubectl edit secret elastic-credentials`

# Re‑create the secret with the new values (repeat step 2)

# Upgrade the Helm release
helm upgrade logging ./platform/charts/elasticsearch-kibana \
  -n mid-cbf-monitoring \
  -f platform/elasticsearch.yaml \
  -f platform/kibana.yaml \
  --wait --wait-for-jobs --timeout 10m
```

The chart reconciles the new passwords within Elasticsearch. Ensure that the Filebeat agents are updated with the new `filebeat_writer` password.

---

**Expected flow**
After a successful deployment: Prometheus scrapes Telegraf, Telegraf receives PDU JSON pushes, Filebeat forwards logs to Elasticsearch, and Kibana provides a user interface for log analysis. If any component fails, consult the Helm release status and examine pod logs in the `mid-cbf-monitoring` namespace.
