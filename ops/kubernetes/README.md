# Kubernetes test environment

2026-10-21: created on dragonvm; Kubernetes `v1.37.1` node Ready with containerd `2.3.4`. Live checks passed for nodes/system pods, cluster DNS, Service traffic and PVC persistence across separate writer/reader pods. The corrected run exited successfully; both smoke namespaces and their PVs are gone. The default context remains `monitoring`.

The initial smoke attempt exposed a BusyBox short-name DNS lookup exit-status issue despite a valid service answer. Absolute DNS names fixed the harness; the corrected run passed.

Run these scripts on `dragonvm` as the user with working Docker access. Requires Docker and minikube; a separate `kubectl` installation is unnecessary. Downloads require internet access.

```sh
./ops/kubernetes/bootstrap.sh
# Repeat only the live checks:
./ops/kubernetes/verify.sh
```

Bootstrap creates or starts the dedicated `fhs-test` minikube profile: Docker driver, containerd, four CPUs, 4096 MiB RAM, Kubernetes `v1.37.1`. Override the version with `KUBERNETES_VERSION` when creating a cluster. Existing profiles, containers and the default kubeconfig context are preserved. Every Kubernetes command names the `fhs-test` context explicitly. The persistent workspace namespace is `fhs-test`.

The checks wait for ready nodes and system pods, resolve cluster DNS, fetch an HTTP response through a Service from another pod, and write/read a dynamically provisioned PVC from separate pods. Each run creates a unique `fhs-smoke-*` namespace, then deletes it and its test resources on exit. A cleanup failure prints the namespace for inspection. Images use `busybox:1.37.0`; pulls and cluster waits can fail if internet access is unavailable. No host ports, host networking, or DHCP services are configured.

```sh
# Inspect this cluster without changing the default context:
minikube -p fhs-test kubectl -- --context=fhs-test get nodes
minikube -p fhs-test kubectl -- --context=fhs-test get pods -A
```

NetBox, Grafana, Telegraf and Bifrost deployment is deferred. `scripts/deploy-bifrost-container.sh` expects `bifrost-infra`, unavailable in the experimental snapshot but tracked in the original checkout. Adapt its privileged containers, host networking, real inventory and DHCP settings before disposable VM use. Future Bifrost tests need an isolated provisioning network: do not expose DHCP/PXE to the real LAN. Kubernetes smoke checks do not validate provisioning or physical hardware.

See [test environment plan](../../docs/test-environment-plan.md) for status and follow-up scope.
