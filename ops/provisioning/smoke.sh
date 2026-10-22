#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
compose=(docker compose -f compose.json)
# This entry point owns the disposable project and always removes it afterward.
trap '"${compose[@]}" down' EXIT
"${compose[@]}" up -d --pull never
"${compose[@]}" exec -T bifrost-prep sh -ec 'test "$(cat /lab/nodes.json)" = "{}"; test -d /bifrost/playbooks'
"${compose[@]}" exec -T bifrost-prep /var/lib/kolla/venv/bin/python - < api-smoke.py
