#!/usr/bin/env bash
# Independent monitoring releases in the isolated fhs-test lab.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
NAMESPACE=fhs-platform
HELM_BIN=${HELM_BIN:-$HOME/.local/bin/helm}
k() { minikube -p fhs-test kubectl -- --context=fhs-test -n "$NAMESPACE" "$@"; }
h() { "$HELM_BIN" --kube-context fhs-test --namespace "$NAMESPACE" "$@"; }
install() {
  local release=$1 chart=$2 version=$3 values=$4
  h upgrade --install "$release" "$chart" --version "$version" -f "$ROOT/platform/$values.yaml" -f "$ROOT/ops/platform/monitoring-values/$values.yaml" --wait --wait-for-jobs --timeout 12m
}
case ${1:-deploy} in
  deploy)
    "$HELM_BIN" repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
    "$HELM_BIN" repo add influxdata https://helm.influxdata.com/ >/dev/null
    "$HELM_BIN" repo add grafana-community https://grafana-community.github.io/helm-charts >/dev/null
    "$HELM_BIN" repo update >/dev/null
    install prometheus prometheus-community/prometheus 29.35.0 prometheus
    install telegraf influxdata/telegraf 1.8.77 telegraf
    install grafana grafana-community/grafana 13.2.7 grafana
    h upgrade --install elastic "$ROOT/platform/charts/elasticsearch-kibana" -f "$ROOT/platform/elasticsearch.yaml" -f "$ROOT/platform/kibana.yaml" -f "$ROOT/ops/platform/monitoring-values/elasticsearch.yaml" --wait --wait-for-jobs --timeout 12m
    ;;
  test) exec "$ROOT/ops/platform/monitoring-test.sh" ;;
  *) echo 'usage: monitoring-deploy.sh [deploy|test]' >&2; exit 2 ;;
esac
