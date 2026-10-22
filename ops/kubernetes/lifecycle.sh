#!/usr/bin/env bash
# Manage only the persistent test cluster; never the host operating system.
set -euo pipefail
profile=fhs-test
script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
case "${1:-}" in
  up)
    command -v minikube >/dev/null
    command -v docker >/dev/null
    docker info >/dev/null
    minikube start --profile="$profile" --driver=docker --container-runtime=containerd \
      --cpus=4 --memory=6144 --kubernetes-version="${KUBERNETES_VERSION:-v1.37.1}" \
      --keep-context --interactive=false --wait=all --wait-timeout=5m
    minikube -p "$profile" kubectl -- --context="$profile" --request-timeout=30s \
      create namespace fhs-test --dry-run=client -o yaml | \
      minikube -p "$profile" kubectl -- --context="$profile" --request-timeout=30s apply -f -
    ;;
  down)
    minikube stop --profile="$profile" --keep-context-active
    ;;
  status)
    minikube status --profile="$profile"
    ;;
  test)
    "$script_dir/verify.sh"
    ;;
  *)
    echo "Usage: $0 {up|down|status|test}" >&2
    exit 2
    ;;
esac
