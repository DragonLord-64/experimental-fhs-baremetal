#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[[ $(hostname) == dragon-lord-Virtual-Machine ]] || { echo 'Run on dragonvm only.' >&2; exit 1; }
kubectl_lab() { minikube -p fhs-test kubectl -- --context=fhs-test "$@"; }
case "${1:-up}" in
  render) python3 render.py ;;
  up|apply)
    python3 -m unittest discover -s tests -v
    python3 preflight.py
    if [[ ${1:-up} == up ]]; then
      ./build.sh
    python3 - <<'IMAGES'
import json, subprocess
for image in json.load(open("images.json")).values():
    subprocess.run(["minikube", "-p", "fhs-test", "image", "load", "--daemon=true", image], check=True)
IMAGES
    fi
    mkdir -p .runtime
    python3 render.py > .runtime/rendered.json
    python3 namespace-guard.py
    python3 -c 'import json; print(json.dumps(json.load(open(".runtime/rendered.json"))["items"][0]))' | kubectl_lab apply -f -
    python3 apply.py
    kubectl_lab -n fhs-emulators rollout status deployment/fhs-emulator --timeout=180s
    kubectl_lab -n fhs-emulators rollout status deployment/cisco-emulator --timeout=90s
    HELM_BIN=${HELM_BIN:-$HOME/.local/bin/helm}
    python3 integration.py
    "$HELM_BIN" --kube-context fhs-test --namespace fhs-platform upgrade telegraf influxdata/telegraf --version 1.8.77 --reuse-values -f .runtime/telegraf-overlay.json --wait --timeout 3m
    "$HELM_BIN" --kube-context fhs-test --namespace fhs-platform upgrade prometheus prometheus-community/prometheus --version 29.35.0 --reuse-values -f .runtime/prometheus-overlay.json --wait --timeout 3m
    python3 reload.py
    python3 verify.py
    ;;
  test) python3 verify.py ;;
  reset)
    kubectl_lab -n fhs-emulators rollout restart deployment/fhs-emulator deployment/cisco-emulator
    kubectl_lab -n fhs-emulators rollout status deployment/fhs-emulator --timeout=180s
    kubectl_lab -n fhs-emulators rollout status deployment/cisco-emulator --timeout=90s
    python3 verify.py
    ;;
  down)
    # Exact owned namespace; never touches the platform or another profile.
    python3 namespace-guard.py
    HELM_BIN=${HELM_BIN:-$HOME/.local/bin/helm}
    python3 integration.py --remove
    "$HELM_BIN" --kube-context fhs-test --namespace fhs-platform upgrade telegraf influxdata/telegraf --version 1.8.77 --reuse-values -f .runtime/telegraf-overlay.json --wait --timeout 3m
    "$HELM_BIN" --kube-context fhs-test --namespace fhs-platform upgrade prometheus prometheus-community/prometheus --version 29.35.0 --reuse-values -f .runtime/prometheus-overlay.json --wait --timeout 3m
    python3 reload.py
    kubectl_lab delete namespace fhs-emulators --ignore-not-found --wait=true
    # A later install must capture a fresh baseline, including operator changes.
    rm -f .runtime/prometheus-before.json .runtime/telegraf-before.json
    ;;
  *) echo 'Usage: deploy.sh [up|apply|test|reset|down|render]' >&2; exit 2 ;;
esac
