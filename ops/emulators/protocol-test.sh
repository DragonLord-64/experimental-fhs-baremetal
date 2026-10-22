#!/usr/bin/env bash
# Standalone actual Telegraf and node exporter contracts; no cluster mutation.
set -euo pipefail
cd "$(dirname "$0")"
[[ $(hostname) == dragon-lord-Virtual-Machine ]] || { echo 'Run on dragonvm only.' >&2; exit 1; }
python3 fixture.py --write
mkdir -p .runtime
cleanup() { docker rm -f fhs-protocol-sender fhs-protocol-node fhs-protocol-telegraf >/dev/null 2>&1 || true; }
for name in fhs-protocol-sender fhs-protocol-node fhs-protocol-telegraf; do
  if docker inspect "$name" >/dev/null 2>&1; then echo "Existing container $name; refusing to replace it." >&2; exit 1; fi
done
finish() {
  for name in fhs-protocol-sender fhs-protocol-node fhs-protocol-telegraf; do
    docker inspect --format '{{json .State}}' "$name" > ".runtime/$name-state.json" 2>/dev/null || true
    docker logs "$name" > ".runtime/$name.log" 2>&1 || true
  done
  cleanup
}
trap finish EXIT
# Shared isolated network namespace: loopback only, no host/LAN access.
docker run -d --name fhs-protocol-telegraf --network=none --memory=256m --cpus=.25 --read-only --user 65532:65532 --cap-drop=ALL --security-opt=no-new-privileges \
  -v "$PWD/tests/telegraf.conf:/etc/telegraf/telegraf.conf:ro" \
  docker.io/library/telegraf:1.40.1@sha256:e91237482edcb054c81571923c6b7cf64f06ed6087a2f9cf0bd3bc2cd8c0ed61 >/dev/null
node_image=$(python3 -c 'import json; print(json.load(open("images.json"))["node"])')
docker run -d --name fhs-protocol-node --network=container:fhs-protocol-telegraf --memory=48m --cpus=.1 --read-only --user 65532:65532 --cap-drop=ALL --security-opt=no-new-privileges \
  -v "$PWD/fixtures:/fixtures:ro" "$node_image" \
  --collector.disable-defaults --collector.textfile --collector.textfile.directory=/fixtures --web.listen-address=:9100 >/dev/null
docker run -d --name fhs-protocol-sender --network=container:fhs-protocol-telegraf --memory=48m --cpus=.1 --read-only --cap-drop=ALL --security-opt=no-new-privileges \
  -v "$PWD/fixtures:/fixtures:ro" fhs-lab/cisco-emulator:1 --target=127.0.0.1:57000 --interval=10s >/dev/null
expected=$(python3 -c 'import json; t=json.load(open("fixtures/topology.json")); print(sum(len(s["links"]) for s in t["switches"]))')
for attempt in $(seq 1 60); do
  docker run --rm --network=container:fhs-protocol-telegraf --memory=16m --cpus=.1 busybox:1.37.0 wget -qO- http://127.0.0.1:9273/metrics > .runtime/telegraf.prom || true
  if [[ $(grep -c '^nexus_lldp_id{' .runtime/telegraf.prom || true) == "$expected" ]]; then break; fi
  sleep 1
done
docker run --rm --network=container:fhs-protocol-telegraf --memory=16m --cpus=.1 busybox:1.37.0 wget -qO- http://127.0.0.1:9100/metrics > .runtime/node.prom
python3 - <<'PY'
import json,re
from pathlib import Path
fixture=json.loads(Path('fixtures/topology.json').read_text())
raw=Path('.runtime/telegraf.prom').read_text()
node=Path('.runtime/node.prom').read_text()
for switch in fixture['switches']:
 for link in switch['links']:
  rows=[line for line in raw.splitlines() if line.startswith('nexus_lldp_id{') and f'source="{switch["name"]}"' in line and f'interface="{link["local_port"]}"' in line]
  assert len(rows)==1,rows
  assert f'sysName="{link["neighbor"]["name"]}"' in rows[0],rows
  assert f'portIdV="{link["remote_port"]}"' in rows[0],rows
  assert rows[0].endswith(' 1'),rows
for host in fixture['hosts']:
 for link in host['interfaces']:
  if host['telemetry']!='missing':
   assert f'address="{link["node_mac"]}"' in node
  else:
   assert f'fhs_name="{host["name"]}"' not in node
assert 'node_textfile_scrape_error 0' in node
assert 'node_cpu_seconds_total' not in node
assert '# TYPE nexus_lldp_id untyped' in raw or '# TYPE nexus_lldp_id gauge' in raw
print('PASS actual Cisco GPB-KV gRPC -> Telegraf LLDP labels, neighbor gauge, node textfile interfaces')
PY
for name in fhs-protocol-sender fhs-protocol-node fhs-protocol-telegraf; do
  docker stats --no-stream --format '{{json .}}' "$name"
  id=$(docker inspect --format '{{.Id}}' "$name")
  path="/sys/fs/cgroup/system.slice/docker-$id.scope"
  if [[ -r "$path/memory.current" ]]; then
    printf '%s\n' "$name cgroup"
    cat "$path/memory.current" "$path/memory.peak"
    grep -E '^(anon|inactive_file) ' "$path/memory.stat"
  fi
done
