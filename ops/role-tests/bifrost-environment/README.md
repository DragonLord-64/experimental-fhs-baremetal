# Bifrost environment patch checks

```bash
python3 -m unittest discover -s ops/role-tests/bifrost-environment -v
```

Synthetic checks cover GEN_EMAIL import failures, continued diagnostics after an
import failure, private package snapshots, release constraints, broken/conflicting constraint files, combined three-package
repair and
stopping before further updates after bootstrap failure. Configuration refuses broken environments and disables reinstall/image steps.
Generated image constraints preserve the release dependency set while replacing
the pip/certifi pins. Package operations in these unit checks are mocked; these checks do not establish compatibility with a deployed Kolla image.
