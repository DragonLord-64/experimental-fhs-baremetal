#!/usr/bin/env bash
# Build-time installation only; no runtime package mutation.
set -euo pipefail
image=${NETBOX_IMAGE:-fhs/netbox-inventory:4.7.0-2.7.1}
context=$(cd "$(dirname "$0")" && pwd)
case ${1:-build} in
  build) docker build -t "$image" "$context" ;;
  --lab) docker build -t "$image" "$context"; minikube -p fhs-test image load "$image" ;;
  --push) docker build -t "$image" "$context"; docker push "$image" ;;
  *) echo 'Usage: build.sh [build|--lab|--push]' >&2; exit 2 ;;
esac
