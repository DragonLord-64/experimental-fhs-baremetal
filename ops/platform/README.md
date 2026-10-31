# Platform lab

Use the existing `fhs-test` cluster on dragonvm. Inspect it before running a
scoped test; the default context is unrelated:

```bash
minikube -p fhs-test kubectl -- --context=fhs-test get pods,svc -A
```

The delivered source is the [single-release platform chart](../../platform/charts/fhs-platform/README.md).
Site overrides are in [values-provisioning.yaml](../../platform/values-provisioning.yaml).
Keep lab namespace, storage/resource overrides and private credentials outside
that copied source. Review those overrides before applying a chart to the lab.

## Checks

```bash
python3 -m unittest discover -s ops/platform/umbrella -p 'test_*.py' -v
python3 -m unittest discover -s ops/platform/inventory-alignment -p 'test_deployment.py' -v
```

These render the delivered chart; they do not deploy it. For live checks, use
[native importer acceptance](inventory-alignment/README.md),
[logging checks](logging/README.md) and the current
[provisioning/security validation](../security-provisioning/VALIDATION.md).
The [cluster operations guide](../kubernetes/README.md) covers access and retained
storage. Preserve existing releases, PVCs, credentials and node storage when
changing test source.

Dated results from the former separate-release lab remain in
[platform validation](VALIDATION.md) and
[monitoring validation](monitoring-validation.md). Those historical commands
are not current deployment instructions. Removing their source scripts does
not uninstall running releases or remove stored data.
