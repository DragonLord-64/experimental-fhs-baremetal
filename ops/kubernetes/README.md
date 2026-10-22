# Persistent Kubernetes test lab

2026-10-21: created on dragonvm; Kubernetes `v1.37.1` node Ready with containerd `2.3.4`. Live checks passed for nodes/system pods, cluster DNS, Service traffic and PVC persistence across separate writer/reader pods. The corrected run exited successfully; both smoke namespaces and their PVs are gone. The default context remains `monitoring`.

The initial smoke attempt exposed a BusyBox short-name DNS lookup exit-status issue despite a valid service answer. Absolute DNS names fixed the harness; the corrected run passed.

Run these scripts on `dragonvm` as the user with working Docker access. Requires Docker and minikube; a separate `kubectl` installation is unnecessary. Downloads require internet access.

```sh
./ops/kubernetes/lifecycle.sh up      # create or resume the lab
./ops/kubernetes/lifecycle.sh status
./ops/kubernetes/lifecycle.sh test    # smoke checks against the running lab
./ops/kubernetes/lifecycle.sh down    # stop this cluster, retain its data
```

`up` creates or starts the dedicated `fhs-test` minikube profile: Docker driver, containerd, four CPUs, 4096 MiB RAM, Kubernetes `v1.37.1`. Override the version with `KUBERNETES_VERSION` when creating a cluster. Existing profiles, containers and the default kubeconfig context are preserved. Every Kubernetes command names the `fhs-test` context explicitly. The persistent workspace namespace is `fhs-test`. `up` waits for cluster readiness but does not run smoke checks. `bootstrap.sh` remains a compatibility entry point for `up` followed by `test`; `verify.sh` also runs the same checks directly.

`down` stops only the `fhs-test` minikube cluster. Bring it back with `up`; cluster objects and local PVC data are retained. This is a single-node lab with VM-local hostPath storage, without HA or a backup guarantee. Back up important data outside the VM. Do not delete the profile or VM to stop work. There is no delete/reset helper.

2026-10-21: before full-stack deployment, `down` took 7.62 seconds and `up` 48.2 seconds. A PVC marker survived stop/start and a fresh pod read it; post-resume smoke checks passed. Host uptime, monitoring containers and default context were preserved. Host restart/disaster recovery are untested; a full stack may resume more slowly.

The test exposed minikube's [provisioner-identity reclamation issue](https://github.com/kubernetes/minikube/issues/16140): an older PV remained `Released` after PVC deletion following restart. The owned marker/probe fixtures were reclaimed after checking their ownership and current provisioner identity; no global repair is automated. Choose stable reclaim/storage behavior before full-stack destructive lifecycle tests.

Run integration tests on dragonvm, with local orchestration; keep the environment close to the user's deployment.

The checks wait for ready nodes and system pods, resolve cluster DNS, fetch an HTTP response through a Service from another pod, and write/read a dynamically provisioned PVC from separate pods. Each run creates a unique `fhs-smoke-*` namespace, then deletes it and its test resources on exit. A cleanup failure prints the namespace for inspection. Images use `busybox:1.37.0`; pulls and cluster waits can fail if internet access is unavailable. No host ports, host networking, or DHCP services are configured.

```sh
# Inspect this cluster without changing the default context:
minikube -p fhs-test kubectl -- --context=fhs-test get nodes
minikube -p fhs-test kubectl -- --context=fhs-test get pods -A
```

NetBox, Grafana, Telegraf and Bifrost deployment is deferred. `scripts/deploy-bifrost-container.sh` expects `bifrost-infra`, unavailable in the experimental snapshot but tracked in the original checkout. Adapt its privileged containers, host networking, real inventory and DHCP settings before disposable VM use. Future Bifrost tests need an isolated provisioning network: do not expose DHCP/PXE to the real LAN. Kubernetes smoke checks do not validate provisioning or physical hardware.

See [test environment plan](../../docs/test-environment-plan.md) for status and follow-up scope.
