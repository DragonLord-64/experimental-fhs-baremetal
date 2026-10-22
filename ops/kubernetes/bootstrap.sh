#!/usr/bin/env bash
# Run on dragonvm as the user with Docker access.
set -euo pipefail
profile=fhs-test
version=${KUBERNETES_VERSION:-v1.37.1}
command -v minikube >/dev/null
command -v docker >/dev/null
docker info >/dev/null
minikube start --profile="$profile" --driver=docker --container-runtime=containerd \
  --cpus=4 --memory=4096 --kubernetes-version="$version" --keep-context \
  --interactive=false --wait=all --wait-timeout=5m
minikube -p "$profile" kubectl -- --context="$profile" create namespace fhs-test \
  --dry-run=client -o yaml | minikube -p "$profile" kubectl -- --context="$profile" apply -f -
"$(dirname "$0")/verify.sh"
