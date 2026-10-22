# Monitoring emulators

Run on dragonvm after [the platform](../platform/README.md) is ready:

```sh
./ops/emulators/deploy.sh             # build, load images, apply, integrate, verify
./ops/emulators/deploy.sh test
./ops/emulators/deploy.sh apply       # reuse already loaded images; apply/integrate/verify
./ops/emulators/deploy.sh reset       # restart these fixtures; counters reset
./ops/emulators/deploy.sh down        # remove own scrape jobs, alias and namespace
```

Requires Docker, minikube, Python 3 with PyYAML and Helm (`~/.local/bin/helm`, or `HELM_BIN`). All cluster operations name `fhs-test`. Resources live in `fhs-emulators`; additive Helm values update the existing lab `prometheus` and `telegraf` releases in `fhs-platform`. Existing jobs, inputs, rules and outputs are preserved. These additions must be reapplied after a base platform redeploy. Integration waits for the Prometheus ConfigMap projection, explicitly reloads its enabled lifecycle endpoint, then checks the loaded scrape jobs and static targets/labels. Fixture checksums roll the two emulator pods when their startup data changes. Manifests use server-side apply to avoid copying the large ConfigMap into a last-applied annotation. One-time fixture migration verifies the ownership label and unchanged client-side baseline before forcing ownership of that ConfigMap only; subsequent updates and other resources never force conflicts. A resource-version check rejects intervening ConfigMap edits. Saved release values/builds/captures stay ignored in `.runtime/`.

`config.json` defaults to **shared** mode: VCCUnit1..4 and FSPUnit1..3: 16 distinct FHS identities, 7 switch identities and 12 mesh links (56 LLDP records; 12 present FHS and four missing). Each VCC unit has one FHS; each FSP unit has four. Every VCC switch connects to every FSP switch. For bounded integration use `EMULATOR_CONFIG=/absolute/path/bounded-config.json ./ops/emulators/deploy.sh` with `{"mode":"shared","vcc_units":1,"fsp_units":3}`; use the same environment for test/reset. Other modes are rejected. `config-full.json` retains the optional 24 VCC / 27 FSP canonical reference via `EMULATOR_CONFIG`; it is not the default acceptance target. Retained host/switch IPs, MACs, FPGA IDs and interface mappings use original full-inventory offsets. `topology.py` is the canonical deterministic inventory; `fixture.py --write` generates its ignored JSON/textfile captures. All addresses/names are synthetic; management IPs use `192.0.2.0/24`.

Two actual SKA FHS exporter processes provide healthy and PSU-fault profiles. Two bounded Go sidecars collect each native `/metrics` response serially (5 seconds after each completed attempt, 4-second timeout) and serve the exact bytes to logical scrape targets. Snapshots expire 15 seconds after successful collection; failed refreshes never extend freshness. Expired or never-collected profiles return HTTP 503 for both metrics and readiness. `X-Exporter-Collected-At` exposes the native collection time; Prometheus sample times remain logical scrape times. This is bounded replay of last-known telemetry, not independent hardware sampling. Native HTTP readiness checks remain enabled. Prometheus scrapes those shared endpoints with distinct `unit`, `role`, `fhs`, `fhs_name` labels. One actual node exporter reads a textfile with the corresponding logical host/interface labels; default host collectors are disabled. One Go sender multiplexes the switch identities over actual Cisco GPB-KV gRPC into the platform's real Telegraf input. There are two pods, six containers, no VMs, privileges, host networking, host devices or hostPath mounts. Services are ClusterIP only.

This is the user-approved fallback for this VM. It preserves monitoring interfaces and identities, but cannot test independent process outages for every logical host. Native/cache/node containers share one pod: any failed readiness check withdraws its Service endpoints for all profiles; this models shared-worker loss as unavailable data, not per-host hardware faults. A measured native FHS worker alone used about 82 MiB working memory: 132 would require about 10.55 GiB before node exporters, switches or the platform. Native 132-FHS/51-switch pods also exceed this node's verified capacity of 110 pods. No application/control commands, signal processing, Tango or dish-data simulation is implemented.

## Scenarios and labels

- **FSPUnit1:** all four FHS scrape targets are unavailable (`up=0`), with no hardware or node series. No zero-filled health metrics. Its switch and mesh links remain healthy.
- **FSPUnit2:** only FHS1 has `sts_psu1_fan{source="PSU1"}=1`; other PSU flags are zero. Other FHS profiles are healthy. Dashboard aggregate policy is **Degraded** for this single PSU fault, even when its tile is red; the emulator does not invent an aggregate health metric.
- **Mesh:** only `VCCUnit1-switch` interface `eth1/1/3` and its peer `FSPUnit3-switch` interface `eth1/1/1` are down. These are the two ends of one link. Every other monitored interface is up. Each FHS has two matching node interfaces (`enp1s0f0`, `enp1s0f1`). Internal host links use physical ports 21–24; mesh links use ports 1–7 with four breakout interfaces per port.

FHS job: `fhs-emulator`. Example `nic_temperature_celcius{unit="FSPUnit2",fhs="FHS1",source="NIC"}=50` (upstream spelling retained). Other component `source` labels remain native (`FPGA0`, `FPGA1`, `CPU`, `PSU1`, `PSU2`, etc.). Metric relabeling retains temperatures, fan RPM, power, voltage, status flags, BIST and availability counts; the actual endpoint serves the full exporter schema.

Node job: `node-emulator`. Textfile metrics include `node_uname_info`, memory and `node_network_info/up/carrier/mtu_bytes/speed_bytes`, plus fixed receive/transmit counters. Identity labels: `unit`, `role`, `fhs`, `fhs_name`; network `device` is the local interface, `address` is its unique MAC, `ifalias` is `<switch>:<switch-interface>`. Missing FSPUnit1 hosts are omitted.

Cisco samples traverse gRPC port 57000 and real Telegraf:

```promql
nexus_interfaces_vdcId{source="VCCUnit1-switch",interface="eth1/1/3",operSt="down"} == 1
nexus_lldp_id{source="VCCUnit1-switch",interface="eth1/1/3",sysName="FSPUnit3-switch",portIdV="eth1/1/1"} == 1
```

`dn` retains the native DME path. `nexus_lldp_id` is the neighbor identity/index, with `sysName`, `portIdV`, `chassisIdV`, `mgmtIp` labels, never a counter. Telegraf's built-in LLDP map treats `id` as string; an explicit path-specific `dmes` override retains the official integer attribute so the string attributes can accompany a numeric sample. Whole-DN regex extraction produces the exact interface label. LLDP is a static **last-known** neighbor inventory and remains present on the failed link; it does not simulate LLDP packet expiry. HC interface/VLAN counters increment for healthy links, remain fixed on the failed link and reset with the sender process.

## Validation and sources

```sh
python3 -m unittest discover -s ops/emulators/tests -v
./ops/emulators/build.sh             # bounded VM compiler + official protobuf wire/cache tests
./ops/emulators/build-cache.sh       # changed cache image only; supervisor loads it before apply
./ops/emulators/protocol-test.sh     # real Telegraf + node exporter, isolated loopback only
./ops/emulators/deploy.sh test       # actual exporters -> Telegraf -> Prometheus labels/values
python3 ops/emulators/lifecycle-check.py # supervisor-only reset/down/restoration/reapply proof
python3 ops/emulators/platform-check.py # read-only NetBox/Grafana application checks
```

`preflight.py` requires 384 MiB measured cluster cgroup headroom. Runtime requests/limits are budgets, not measured use. See [validation evidence](VALIDATION.md); full Kubernetes integration is not established by the standalone protocol probe.

Integration copies observed values before editing. Cleanup restores the recorded Prometheus-output string-label setting and LLDP overrides, retaining unrelated output fields; changed output counts require manual review. Successful removal clears the saved baseline for the next install. The output string-label setting affects the shared Telegraf receiver while installed; platform preservation needs live checks. FPGA component labels remain upstream `FPGA0`/`FPGA1`, scoped by logical FHS scrape labels; shared worker card names do not establish independent card processes.

- [SKA FHS exporter 0.0.7](https://gitlab.com/ska-telescope/ska-mid-cbf/host-software/ska-mid-cbf-fhs-prometheus-exporter/-/tree/26f95899deeb0c90d42688ae1ebdc7dc97eaa33e), source commit `26f95899deeb0c90d42688ae1ebdc7dc97eaa33e`. Actual image digest pinned in `images.json`. Copied four upstream YAML fixtures retain [BSD-3-Clause license](fixtures/FHS-LICENSE). Adaptations: list-valued FEC info attributes normalized to string zero to repair demonstrated HTTP 500; healthy readiness/FEC/temperature values; separate PSU1 fan-fault fixture. No exporter source copied or changed. The upstream image is approximately 1.98 GB unpacked; first pull is substantial.
- [Cisco official protobufs](https://github.com/cisco-ie/nx-telemetry-proto/tree/f64c045c77df), Go module pinned to `f64c045c77df`; [Apache-2.0 license](cisco/PROTOCOL-LICENSE). [Actual Telegraf 1.40.1 DME parser](https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/inputs/cisco_telemetry_mdt/parser.go) is the receiver contract.
- Cisco official [LLDP paths/attributes](https://developer.cisco.com/docs/cisco-nexus-3000-and-9000-series-nx-api-rest-sdk-user-guide-and-api-reference-release-9-3x/querying-lldp/) and [interface/VLAN counters](https://developer.cisco.com/docs/cisco-nexus-3000-and-9000-series-nx-api-rest-sdk-user-guide-and-api-reference-release-9-2x/querying-interface-and-vlan-counters-and-statistics/). Implemented monitoring subset: `ethpmPhysIf`, `rmonIfHCIn/Out`, `lldpAdjEp`, `l2VlanStats`, `eqptCh`. No NX-API or lldpcli server.
- Real upstream node exporter `v1.9.1`, immutable digest in `images.json`; only textfile collector enabled. Private scratch sender is built locally from the pinned Go module; no upstream publishing.

Standalone HTTP probes use BusyBox 1.37.0 pinned to the cached image digest in `protocol-test.sh` (GPL-2.0-only); no BusyBox source is copied.

Component-health fixture addition: retain actual native `fan1_rpm`, `fan2_rpm`, `prochot_cpu`, `cpu1_thermtrip`, `volt_12v_volts`, `volt_3v_volts`, `watchdog2` and `chassis_intr` through the lab scrape filter. Present logical hosts also expose synthetic `node_hwmon_temp_celsius{chip="nvme_nvme0/1",sensor="temp1"}=36.85` and `node_nvme_info{device="nvme0/1",state="live"}=1`, following reference node-exporter labels and units. Model/firmware/serial values are explicitly synthetic; no production identity is copied. Missing FSPUnit1 hosts remain omitted. These fixtures describe expected monitoring input, not physical storage health.
