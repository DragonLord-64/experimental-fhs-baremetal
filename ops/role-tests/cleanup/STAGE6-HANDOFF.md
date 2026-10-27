# Source cleanup handoff — 2026-10-26

Source stages 1–6 and focused supervisor runtime acceptance are complete for
user review. The existing fhs-test delivered-chart release is deployed at revision
6; actual Service routing and persistent devpi cache checks passed. This is not
proof of production, hardware or real-systemd behavior. See the final acceptance
entry in [EVIDENCE.md](EVIDENCE.md).

## Source diff and transfer

Compared against official development2 `7704587034e7e41f1b1266c109b0e903279617a9`
(stage-1 successful fetch), with worker baseline `a5395d00715ee1a50454fc71e54820901580d7e7`.
This is the completed cleanup's historical baseline. Later official changes and
current copy prerequisites are tracked in [the transfer manifest](TRANSFER.md).
Preserve accepted experimental behavior; do not replace these folders with a
blind upstream copy.

| Source | Deliberate difference retained/delivered |
|---|---|
| manage_users / manage_venvs / SDK / runner | Approved development sudo, shared bittware/666 membership without replacing groups, fresh-session access, permission repair after installation, meaningful runner install check |
| DPDK / FPGA | Whole-procedure retry and input success record, clean-build triggers, shared hugepage settings, root-owned build source, explicit firmware gate, no host reboot |
| node / network / CIS callers | Prepare only, no join; pinned versions, containerd change detection; MAC-specific networkd and targeted legacy cleanup; timesyncd; effective Linux policy group and safe audit actions |
| gRPC / Poetry / BIST | One controller tag, integrated pinned Poetry, reviewed package/lock inputs and per-controller config; no-change install/service skip; retired standalone Poetry; installation-only BIST |
| exporter / Prometheus / Filebeat | Real pinned packages, isolated protected exporter code; conditional install/restart and binary validation; preserve delegated same-package Filebeat setup and separate credentials |
| distribution roles / site | Keep existing APT signatures/cache, pip and Git configuration; role selection tags in site, internal tags only functional/safety options; final rsync tasks outside FPGA role |
| platform | Preserve existing APT deployment/config/PVC. Add pinned public devpi and Squid images, devpi retained claim, internal-only service defaults and restricted Git destinations; no custom build required |
| docs | Preserve consolidated role READMEs/includes; update commands, callers, prerequisites and observed limits rather than restoring duplicate upstream pages |

Transfer roles/docs/playbooks together, including deletions and new task files.
Carry site/provision callers, archive gRPC caller and monitoring download caller.
Also transfer `platform/charts/fhs-platform` additions and deliberately merge the
sanitized inventory policy/group/shared-identity settings from stages 1–3.
Configure reachable `apt_cache_url`, `pip_index_url`, `git_proxy_url`; no inventory
endpoint/credential was invented here. Supply approved artifacts, matching lock
pairs when overriding package sources, key directory, exact runtime/cluster
versions, DNS/NTP/network inputs and protected service credentials. Review rsync
daemon configuration before real use. Never copy private inventory/captures.

Keep ops fixtures/evidence, orchestration and controller files outside official
transfer. NetBox JSON transfer/Nexus changes in the working tree are separate.
Queue cancellation, final source/link check, publication and review are caller-owned.

## Supervisor deployment and basic acceptance

Use the existing delivered-chart lab release; last evidence names release and
namespace `fhs-inventory-alignment`. Inspect first. Do not use the default context
or create a cluster. If SSH fails, follow the root WOL protocol. No host lifecycle,
firmware, firewall or production-inventory operations.

On the orchestration checkout with the lab kubeconfig (or on dragonvm checkout):

```bash
kubectl --context fhs-test -n fhs-inventory-alignment get deployments,services,pvc
helm list --kube-context fhs-test -n fhs-inventory-alignment
# Preserve all existing site/lab overrides privately; do not print or commit them.
umask 077
helm get values fhs-inventory-alignment --kube-context fhs-test \
  -n fhs-inventory-alignment -o yaml > /tmp/fhs-stage6-existing-values.yaml
cat > /tmp/fhs-stage6-proxies.yaml <<'YAML'
devpi:
  enabled: true
  persistence:
    storageClass: standard
    size: 1Gi
gitProxy:
  enabled: true
YAML
helm upgrade fhs-inventory-alignment platform/charts/fhs-platform \
  --kube-context fhs-test -n fhs-inventory-alignment \
  -f /tmp/fhs-stage6-existing-values.yaml -f /tmp/fhs-stage6-proxies.yaml \
  --post-renderer /home/dragon-lord/fhs-role-cleanup-20261026/scoped-render.py \
  --wait --wait-for-jobs --timeout 20m
kubectl --context fhs-test -n fhs-inventory-alignment rollout status \
  deployment/fhs-inventory-alignment-devpi --timeout=120s
kubectl --context fhs-test -n fhs-inventory-alignment rollout status \
  deployment/fhs-inventory-alignment-git-proxy --timeout=120s
kubectl --context fhs-test -n fhs-inventory-alignment get services,pvc
```

If the inspected release differs, use its actual release/namespace consistently
in these commands and service names. Preserve APT PVC and overrides, particularly
storage class; do not redeploy from defaults alone. Check lab memory capacity
for devpi's 1Gi limit before rollout. Private values may contain credentials.
Registry access prerequisites (no image build):

- `docker.io/jonasal/devpi-server@sha256:5e6768442a738251a760acac91f595a07e80cfac28fcfaed098c3e0e544cf46e`
- `docker.io/ubuntu/squid@sha256:6a097f68bae708cedbabd6188d68c7e2e7a38cedd05a176e1cc0ba29e3bbe029`
- Existing APT digest and other chart images/dependencies remain unchanged.
- devpi needs outbound verified HTTPS to PyPI/files.pythonhosted.org. Squid needs
  DNS/443 access to allowed Git domains; no TLS interception. Existing APT needs
  its configured repository access. Provisioning clients need approved reachability.

Forward services locally in separate terminals, bound to loopback:

```bash
kubectl --context fhs-test -n fhs-inventory-alignment port-forward \
  service/fhs-inventory-alignment-devpi 13141:3141
kubectl --context fhs-test -n fhs-inventory-alignment port-forward \
  service/fhs-inventory-alignment-git-proxy 13128:3128
kubectl --context fhs-test -n fhs-inventory-alignment port-forward \
  service/fhs-inventory-alignment-apt-cacher 13142:3142
```

Then run bounded client fetches (one actual installed package and Git objects):

```bash
curl --fail --max-time 30 http://127.0.0.1:13141/+status -o /dev/null
python3 -m pip install --no-deps --target /tmp/fhs-stage6-package \
  --index-url http://127.0.0.1:13141/root/pypi/+simple/ six==1.17.0
PYTHONPATH=/tmp/fhs-stage6-package python3 -c 'import six; assert six.__version__ == "1.17.0"'
git init /tmp/fhs-stage6-git
# Bypass any unrelated system URL-rewrite policy in a disposable client if needed.
git -C /tmp/fhs-stage6-git -c http.proxy=http://127.0.0.1:13128 \
  fetch --depth=1 --filter=blob:none https://gitlab.com/gitlab-org/cli.git HEAD
curl --fail --max-time 60 --proxy http://127.0.0.1:13142 \
  http://deb.debian.org/debian/pool/main/h/hello/hello_2.10-3_amd64.deb \
  -o /tmp/fhs-stage6-hello.deb
dpkg-deb --info /tmp/fhs-stage6-hello.deb
```

Verify service DNS/endpoints from an existing disposable client as well; local
port-forward alone bypasses the Service data plane. Check `/var/devpi` is the
Bound claim mount and contains initialized state/cache, plus unchanged APT cache
claim identity. Do not claim Kubernetes persistence from the tmpfs Docker test.
No need for an outage matrix, cluster lifecycle test or hardware probe. Record
actual readiness, memory, fetch and PVC results before declaring overall completion.

## Observed nondeployment results and limits

See [EVIDENCE.md](EVIDENCE.md) for exact commands/results, including earlier
stages' fixture failures and corrections; [PACKAGING.md](PACKAGING.md) records
real selected-release controller analysis/recommendation. Stage 6: Helm lint and
template, rendered contracts, targeted syntax/site-provision parsing, tag listing,
inert actual-main firmware gate cases, actual devpi package install, Squid parse
and real Git fetch, APT package fetch, and Sphinx HTML passed. Sphinx has five
known warnings (external Python inventory and four existing NetBox README links).

Worker-only limits below are superseded for chart rollout, PVC persistence and
Service routing by the final supervisor acceptance. Remaining limits: production credentials,
real systemd/boot/kernel/network/CIS apply, internal NTP, proprietary SDK, FPGA/NIC
or firmware validation. No application correctness/hardware reading claims.
Community image digest pinning identifies tested bytes, not a security audit.
The default proxy endpoints are unauthenticated and lack TLS listeners; keep
approved provisioning access or supply HTTPS termination for pip. Existing devpi
volumes retain their existing credentials/policy; no migration is attempted.
