# Discovery, HW home and setup-only logs

Portable settings: [configuration](../../../platform/charts/fhs-platform/CONFIGURATION.md).
The [shared chart README](../../../platform/charts/fhs-platform/README.md) remains
byte-identical to official `development2` commit `7b0a306b091306534eef9dfa5872e23547387d7e`.
No official repository is changed or pushed.

```bash
python3 -m unittest discover -s ops/platform/discovery-portal-setup -p 'test_*.py'
python3 ops/platform/discovery-portal-setup/acceptance.py \
  --context fhs-test --namespace fhs-discovery-portal-test \
  --report /tmp/fhs-discovery-portal-setup-acceptance.json
```

The supervised harness copies only chart/importer/check sources to `dragonvm`.
It checks the existing cluster and services, installs the committed private
baseline, runs actual native importers, then upgrades the same release and
checks inventory, exporter refresh, ingress/assets, logging setup and reapply.
It rejects other contexts/namespaces, unowned state and private site values.
A retained failed run can resume with `--resume` on dragonvm; evidence and the
original baseline remain in its recorded temporary directory. A successful or
foreign report cannot authorize resume. It never recreates the cluster.

Baseline: private `8fe1d1788ff87def0824e5dfa9115a02aa3cebeb`; official
`development2` `7b0a306b091306534eef9dfa5872e23547387d7e`.
[Source evidence](source-evidence.json) pins committed chart archives;
`baseline.py --output /tmp/fhs-discovery-baseline` regenerates them without
reading private values. [Template comparison](template-comparison.json) is
render evidence only. Actual results and limits: [validation](VALIDATION.md).

The isolated fixture creates a read-only NetBox discovery principal using the
authentication ORM, and a `prometheus_exporters` multi-select field through the
real REST API. It selects
active devices by that field, exercises two real synthetic exporter listeners,
and verifies independent selection, rename, inactivity, clearing and deletion.
No physical device is contacted. Exporters still require installation on hardware.

The full run requires Helm, minikube, PyYAML, the native importer requirements
and NetBox collection. The checked lab runtime uses `/tmp/fhs-discovery-tools-venv`
and `/tmp/fhs-discovery-collections`. Credentials stay in private stdin/Secrets;
the sanitized report contains fixture evidence and hashes. A legacy importer API
token is bootstrapped only inside the owned test NetBox, using its existing Secret.
