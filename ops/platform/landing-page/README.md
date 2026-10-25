# Installation home

[Issue #13](https://github.com/DragonLord-64/experimental-fhs-baremetal/issues/13).
Extends the existing `landing` service and shared ingress. Settings and local
Markdown file example: [configuration](../../../platform/charts/fhs-platform/CONFIGURATION.md#installation-home).
No application credentials or Kubernetes API access are used by the home.

```bash
PATH=/home/dragon-lord/.local/bin:$PATH python3 -m unittest discover -s ops/platform/landing-page -v
PATH=/home/dragon-lord/.local/bin:$PATH python3 -m unittest discover -s ops/platform/discovery-portal-setup -v
/home/dragon-lord/.local/bin/helm lint platform/charts/fhs-platform
```

Controller-only live check (not run by the worker):

```bash
ops/platform/landing-page/acceptance.py --report /tmp/fhs-landing-page-acceptance.json
```

Lab namespace: `fhs-discovery-portal-test`. Helm release: `mid-cbf-hw`.
Landing Deployment/Service: `mid-cbf-hw-hw-landing`; shared Ingress:
`mid-cbf-hw-web`. Uses the retained private values from the preceding acceptance. Inspects services, capacity and scales first. Upgrades the full chart,
skips unrelated setup Jobs, suspends CronJobs and starts only required services.
Checks root and prefixed pages/scripts through the existing ingress, Markdown,
custom links, cached timestamps and a synthetic endpoint failure/recovery.
Restores original values/scales/CronJobs and removes owned fixtures; retains
sanitized results, HTML responses and private failure diagnostics. A failed
cleanup fails acceptance. It neither reconstructs the baseline nor reruns native
importers: those sources and NetBox/plugin interfaces are unchanged.

2026-10-24: six landing tests, 13 discovery/home tests, three Topology Views
checks and Helm lint passed. The worker also passed ten umbrella checks. Live
acceptance passed in 301.51s: all three managed websites reachable, cached
one-minute failure/recovery, Markdown/custom links, root and prefixed shared
ingress, credential/PVC preservation and original scales/configuration restored.
Browser inspection confirmed the prefixed page and live statuses through ingress.
No production, TLS or physical hardware validation is claimed.

Supervised evidence is retained under ignored
`ops/agent-pipeline/runs/platform-landing-page-recovery-20261024/`. The original
runner stopped because its PATH omitted user-local Helm; the supervisor completed
the configured checks with that PATH corrected. Ingress-transition checks allow
up to 45s for controller convergence. The existing lab cluster container needed
8GiB memory / 10GiB memory-plus-swap; that resource fix is retained. No host or
cluster restart was performed.
