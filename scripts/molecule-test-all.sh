#!/usr/bin/env bash
# Run Molecule tests for every role in the midcbf.fhs collection.
# Activate the venv first:  source .venv/bin/activate
set -euo pipefail

ROLES_DIR="$(cd "$(dirname "$0")/.." && pwd)/collections/ansible_collections/midcbf/fhs/roles"

for role in "$ROLES_DIR"/*/; do
  if [[ -d "$role/molecule" ]]; then
    echo "=== molecule test: $(basename "$role") ==="
    (cd "$role" && molecule test)
  fi
done
