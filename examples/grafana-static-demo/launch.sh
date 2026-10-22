#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
command -v docker >/dev/null 2>&1 || { echo 'Docker with the Compose plugin is required.' >&2; exit 1; }
docker compose version >/dev/null
case "${GRAFANA_PORT:-13000}" in *[!0-9]*|'') echo 'GRAFANA_PORT must be a numeric TCP port.' >&2; exit 1;; esac
if [ "${GRAFANA_PORT:-13000}" -lt 1 ] || [ "${GRAFANA_PORT:-13000}" -gt 65535 ]; then
  echo 'GRAFANA_PORT must be between 1 and 65535.' >&2; exit 1
fi
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-fhs-static-demo}"
docker compose config --quiet
if ! docker compose up --build -d; then
  echo 'Launch failed. Check Docker output above; if the loopback port is occupied, set GRAFANA_PORT to an unused port. Existing resources were preserved.' >&2
  exit 1
fi
# Readiness uses the existing Grafana container; no host curl/Python dependency.
i=0
until docker compose exec -T exporter python -c '
import json, urllib.request
for url in ("http://127.0.0.1:9100/metrics", "http://prometheus:9090/-/ready", "http://grafana:3000/api/health"):
    with urllib.request.urlopen(url, timeout=3) as response:
        body = response.read()
        if url.endswith("health"):
            assert json.loads(body)["database"] == "ok"
'; do
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then echo 'Demo readiness timed out after 60 attempts; inspect docker compose logs.' >&2; exit 1; fi
  sleep 2
done
printf 'Static demo ready: http://127.0.0.1:%s/d/fhs-infra-rack\n' "${GRAFANA_PORT:-13000}"
