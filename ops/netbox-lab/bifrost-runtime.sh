#!/usr/bin/env bash
# Supervisor-only disposable runtime. No implicit image pull, host networking or power actions.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
image='quay.io/openstack.kolla/bifrost-deploy:2026.1-ubuntu-noble@sha256:e6f0e429611d3c4e190633f1b90987f5534768c4f3c9d0eee21f760d86bd22b7'
name=fhs-netbox-lab-bifrost-check
network=fhs-netbox-lab-bifrost-internal
case "${1:-}" in
  inspect) script=inspect-bifrost.py ;;
  check)
    script=bifrost-check.py
    [[ -f "${2:-}" ]] || { echo 'Private generated nodes.json required' >&2; exit 2; }
    ;;
  *) echo 'Usage: bifrost-runtime.sh inspect | check /private/nodes.json' >&2; exit 2 ;;
esac
# Fail rather than replace an existing concurrent resource with the same name.
if docker container inspect "$name" >/dev/null 2>&1 || docker network inspect "$network" >/dev/null 2>&1; then
  echo 'Owned resource name already exists; explicit supervisor recovery required' >&2
  exit 1
fi
created_network=false
created_container=false
cleanup() {
  if "$created_container"; then
    label=$(docker inspect --format '{{ index .Config.Labels "fhs.owner" }}' "$name" 2>/dev/null || true)
    if [[ "$label" == fhs-netbox-lab ]]; then docker rm -f "$name" >/dev/null; fi
  fi
  if "$created_network"; then docker network rm "$network" >/dev/null; fi
}
trap cleanup EXIT
# Docker default bridge is avoided: the only bridge here is internal, without ports.
docker network create --internal --label fhs.owner=fhs-netbox-lab "$network" >/dev/null
created_network=true
docker create --name "$name" --label fhs.owner=fhs-netbox-lab --pull never \
  --network "$network" --user 65534:65534 --read-only --cap-drop ALL \
  --security-opt no-new-privileges:true --pids-limit 64 --memory 256m --cpus .25 \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m -i --entrypoint /var/lib/kolla/venv/bin/python \
  "$image" - >/dev/null
created_container=true
if [[ "$1" == inspect ]]; then
  timeout 120 docker start -ai "$name" < "$script"
else
  python3 - "$2" "$script" <<'PY' | timeout 180 docker start -ai "$name"
import json
from pathlib import Path
import stat
import sys
source = Path(sys.argv[1])
if stat.S_IMODE(source.stat().st_mode) != 0o600:
    raise SystemExit('Export must be private mode0600')
nodes = json.loads(source.read_text())
print('import json\nNODES = json.loads(' + repr(json.dumps(nodes)) + ')')
print(Path(sys.argv[2]).read_text())
PY
fi
