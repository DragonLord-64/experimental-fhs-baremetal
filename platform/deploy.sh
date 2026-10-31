#!/usr/bin/env bash
# Install/upgrade the platform, then export its controller settings.
set -euo pipefail

if (( $# )); then
    echo "Usage: $0 (uses the current Kubernetes context and values-provisioning.yaml)" >&2
    exit 2
fi

platform_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bash "$platform_dir/charts/deploy_upgrage_mid-cbf-hw.sh"
python3 "$platform_dir/charts/export-platform.py" \
    --namespace hw-management --release mid-cbf-hw
