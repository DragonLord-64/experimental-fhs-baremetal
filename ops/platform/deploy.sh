#!/usr/bin/env bash
# Thin lab orchestration; each component remains an independent Helm release.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
helm_bin=${HELM_BIN:-$HOME/.local/bin/helm}
h() { "$helm_bin" --kube-context fhs-test -n fhs-platform "$@"; }
case ${1:-deploy} in
  deploy)
    if (( $# > 2 )) || [[ -n ${2:-} && ${2:-} != --with-bifrost ]]; then echo "Unknown deployment option" >&2; exit 2; fi
    bash "$root/platform/netbox-image/build.sh" --lab
    python3 "$root/ops/platform/prepare.py"
    h upgrade --install netbox-postgresql oci://registry-1.docker.io/bitnamicharts/postgresql --version 18.8.13 -f "$root/platform/netbox-postgresql.yaml" -f "$root/ops/platform/dragonvm/postgresql.yaml" --wait --timeout 8m
    h upgrade --install netbox-valkey oci://registry-1.docker.io/bitnamicharts/valkey --version 6.2.16 -f "$root/platform/netbox-valkey.yaml" -f "$root/ops/platform/dragonvm/valkey.yaml" --wait --timeout 8m
    h upgrade --install netbox oci://ghcr.io/netbox-community/netbox-chart/netbox --version 8.3.67 -f "$root/platform/netbox.yaml" -f "$root/ops/platform/dragonvm/netbox.yaml" --wait --timeout 12m
    "$root/ops/platform/netbox-bootstrap.sh"
    "$root/ops/platform/monitoring-deploy.sh" deploy
    "$0" test
    if [[ ${2:-} == --with-bifrost ]]; then
      image=quay.io/openstack.kolla/bifrost-deploy:2026.1-ubuntu-noble@sha256:e6f0e429611d3c4e190633f1b90987f5534768c4f3c9d0eee21f760d86bd22b7
      if ! docker image inspect "$image" >/dev/null 2>&1; then timeout 300 docker pull "$image"; fi
      "$root/ops/provisioning/smoke.sh"
    fi
    ;;
  test)
    python3 "$root/ops/platform/netbox-test.py"
    "$root/ops/platform/monitoring-deploy.sh" test
    ;;
  *) echo 'Usage: deploy.sh [deploy [--with-bifrost]|test]' >&2; exit 2 ;;
esac
