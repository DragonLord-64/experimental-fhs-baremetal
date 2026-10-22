# Emulator validation — 2026-10-22

Candidate evidence; no emulator Kubernetes deployment or platform Helm change performed at this handoff.

- Local: `python3 -m unittest discover -s ops/emulators/tests -v`: 4 passed. Checks full unit/host/mesh counts, both ends of the single failed link, missing telemetry, unique MACs, additive integration/idempotence, source exporter commands, isolation and ConfigMap size. Python compile and Bash syntax checks passed.
- dragonvm: `build.sh`: official protobuf marshal/unmarshal and all generated neighbor identity checks passed (`go test -mod=readonly ./...`); static scratch image built. Compiler limited to one CPU/512 MiB. Dependencies pinned in `cisco/go.mod`/`go.sum`.
- Actual SKA image `0.0.7` successfully pulled and pinned; approximately 1.98 GB unpacked. Explicit nonroot/read-only invocation bypasses bundled shell startup and REST server. First scrape reproduced HTTP 500 from list-valued FPGA FEC info labels in the upstream fixture. Explicit licensed fixture normalization fixed it: actual HTTP scrape returned 3,385 lines, NIC temperature 50, both FPGA collectors, PSU1 fan flag 1 for the fault fixture, other PSU flags 0 and availability counts 0 unavailable.
- Successful FHS probe cgroup snapshot: `memory.current=149381120`, `inactive_file=63528960`, `anon=81145856`, `memory.peak=165302272` bytes. Working estimate `current-inactive_file=85,852,160` bytes (~81.9 MiB). This includes the brief in-container diagnostic process; it is not a promise of sustained RSS. Earlier reported ~86 MiB used decimal/binary units inconsistently; use these raw bytes for capacity calculations.
- Standalone actual Telegraf `1.40.1` + node exporter `1.9.1` + sender: `protocol-test.sh` passed for 1 VCC/3 FSP and full 24 VCC/27 FSP. Verifies **every** generated LLDP local/source/remote interface/name label, numeric neighbor carrier and all expected node interface MACs; FSPUnit1 node identities absent. Full test waited for all 1,560 LLDP records before asserting, avoiding partial first-flush success.
- Actual decoder discoveries fixed: DME subtree required to promote each DN before grouping; path-specific LLDP integer mapping required because Telegraf's default database turns `id` into a string; whole-DN regex anchoring required for an exact interface label. No direct fabricated Prometheus endpoint replaces the Cisco receiver.

Docker cgroup-derived working memory snapshots (`docker stats --no-stream`), after successful actual protocol assertions:

| Logical inventory | Sender | Node exporter | Separate test Telegraf |
| --- | ---: | ---: | ---: |
| 1 VCC / 3 FSP | 3.133 MiB | 11.45 MiB | 132.7 MiB |
| 24 VCC / 27 FSP | 17.45 MiB | 27.48 MiB | 55.18 MiB |

These are short snapshots with different GC/cache state, not comparative benchmarks or steady-state maxima. Sender/node were bounded at 48 MiB during both probes; test Telegraf at 256 MiB. An initial Telegraf probe at 128 MiB lost its listener; that failed attempt did not establish its exit cause, so no OOM claim is made. Final Kubernetes budgets are FHS workers each 128/192 MiB request/limit, node and sender each 32/64 MiB.

Native capacity cannot fit the complete inventory here: 132 × the measured ~81.9 MiB FHS snapshot is ~10.55 GiB before 132 node exporters, 51 switches, the platform and Kubernetes. The node reports capacity 110 pods; independent 132 FHS plus 51 switch pods would exceed it. Shared mode is explicitly selected in `config.json`. Native scale 5/20/100 was not stress-tested.

VM build/probe evidence: `~/fhs-emulators-build/{build.log,protocol-test.log,protocol-test-full.log,fhs-raw.prom,.runtime/}`. Probe containers were removed by their owned cleanup. No host networking, devices, real inventories, host power operations or upstream pushes were used.

Remaining for the independent issue-3 pipeline: run server-side render/Helm validation; bounded 1/3 actual Kubernetes integration; verify `verify.py` assertions through the running Prometheus; measure cluster/cgroup headroom; expand to 24/27 only if safe; check reset/cleanup/reapply behavior and preserve existing platform checks. Full hardware behavior, long-running resource maxima and independent logical-host process failures remain unverified.
