#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
helm upgrade --install mid-cbf-hw "$script_dir/fhs-platform" \
  --namespace hw-management --create-namespace \
  -f "$script_dir/../values-provisioning.yaml" \
  --wait --wait-for-jobs --timeout 20m "$@"
