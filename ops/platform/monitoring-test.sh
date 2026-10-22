#!/usr/bin/env bash
# Synthetic telemetry and authenticated service checks; run on dragonvm.
set -euo pipefail
k() { minikube -p fhs-test kubectl -- --context=fhs-test --request-timeout=30s -n fhs-platform "$@"; }
pids=()
forward_dir=$(mktemp -d)
cleanup() { for pid in "${pids[@]}"; do kill -- "-$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; done; rm -rf "$forward_dir"; }
trap cleanup EXIT
k rollout status deployment/monitoring-prometheus --timeout=600s
k rollout status statefulset/elastic-elastic --timeout=600s
k rollout status deployment/elastic-elastic-kibana --timeout=600s
k rollout status deployment/switch-telegraf --timeout=180s
k rollout status deployment/monitoring-grafana --timeout=180s
for item in 'monitoring-prometheus PROM_PORT 9090' 'switch-telegraf PDU_PORT 8080' 'switch-telegraf METRICS_PORT 9273' 'monitoring-grafana GRAFANA_PORT 80' 'elastic-elastic ELASTIC_PORT 9200' 'elastic-elastic-kibana KIBANA_PORT 5601'; do
  read -r svc portvar remoteport <<< "$item"
  logfile="$forward_dir/$portvar"
  # kubectl chooses an available loopback port; require its explicit readiness line.
  setsid minikube -p fhs-test kubectl -- --context=fhs-test --request-timeout=30s -n fhs-platform port-forward --address 127.0.0.1 "service/$svc" ":$remoteport" >"$logfile" 2>&1 &
  pid=$!; pids+=("$pid")
  ready=false
  for attempt in $(seq 1 60); do
    if ! kill -0 "$pid" 2>/dev/null; then cat "$logfile" >&2; exit 1; fi
    if grep -q 'Forwarding from 127.0.0.1:' "$logfile"; then ready=true; break; fi
    sleep 1
  done
  if [[ $ready != true ]]; then echo "Port forward failed for $svc" >&2; cat "$logfile" >&2; exit 1; fi
  port=$(sed -n 's/.*Forwarding from 127.0.0.1:\([0-9]*\).*/\1/p' "$logfile" | head -1)
  export "$portvar=$port"
done
export GRAFANA_USER=$(k get secret monitoring-grafana-admin -o jsonpath='{.data.admin-user}' | base64 -d)
export GRAFANA_PASSWORD=$(k get secret monitoring-grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d)
export ELASTIC_PASSWORD=$(k get secret elastic-credentials -o jsonpath='{.data.elastic-password}' | base64 -d)
python3 - <<'PY'
import base64,json,os,time,urllib.request,urllib.parse,urllib.error,uuid
PROM_PORT,PDU_PORT,METRICS_PORT,GRAFANA_PORT,ELASTIC_PORT,KIBANA_PORT=[int(os.environ[n]) for n in ("PROM_PORT","PDU_PORT","METRICS_PORT","GRAFANA_PORT","ELASTIC_PORT","KIBANA_PORT")]

def get(port,path,body=None,auth=None):
 headers={}
 if body is not None: headers['Content-Type']='application/json'
 if auth: headers['Authorization']='Basic '+base64.b64encode(':'.join(auth).encode()).decode()
 req=urllib.request.Request(f'http://127.0.0.1:{port}{path}',data=json.dumps(body).encode() if body is not None else None,headers=headers)
 with urllib.request.urlopen(req,timeout=10) as r:return r.read()
def retry(fn):
 end=time.monotonic()+180
 while True:
  try:return fn()
  except Exception:
   if time.monotonic()>end:raise
   time.sleep(2)
def check(condition):
 if not condition:raise AssertionError('service response did not meet expectation')
pdu_id='synthetic-lab-'+uuid.uuid4().hex[:12]
retry(lambda:get(PDU_PORT,'/pdu',{'pdu_id':pdu_id,'power_watts':123.5}))
retry(lambda:check(b'pdu_power_watts' in get(METRICS_PORT,'/metrics')))
print('PASS synthetic PDU accepted and exported',flush=True)
query=urllib.parse.quote('pdu_power_watts{pdu_id="'+pdu_id+'"}')
def metric(port,path,auth=None):
 d=json.loads(get(port,path,auth=auth));check(any(float(r['value'][1])==123.5 for r in d['data']['result']))
retry(lambda:metric(PROM_PORT,'/api/v1/query?query='+query))
print('PASS Prometheus synthetic metric query',flush=True)
auth=(os.environ['GRAFANA_USER'],os.environ['GRAFANA_PASSWORD'])
check(json.loads(get(GRAFANA_PORT,'/api/health'))['database']=='ok')
retry(lambda:metric(GRAFANA_PORT,'/api/datasources/proxy/uid/prometheus/api/v1/query?query='+query,auth))
print('PASS Grafana health and authenticated datasource query',flush=True)
eauth=('elastic',os.environ['ELASTIC_PASSWORD'])
retry(lambda:check(json.loads(get(ELASTIC_PORT,'/_cluster/health',auth=eauth))['status'] in ('yellow','green')))
retry(lambda:check(json.loads(get(KIBANA_PORT,'/api/status',auth=eauth))['status']['overall']['level']=='available'))
retry(lambda:check(isinstance(json.loads(get(KIBANA_PORT,'/api/spaces/space',auth=eauth)),list)))
try:
 get(ELASTIC_PORT,'/_cluster/health')
except urllib.error.HTTPError as exc:
 check(exc.code==401)
else:
 raise AssertionError('Elasticsearch unexpectedly accepted unauthenticated request')
print('PASS synthetic PDU -> Telegraf -> Prometheus -> Grafana; Elasticsearch/Kibana authenticated health')
PY
