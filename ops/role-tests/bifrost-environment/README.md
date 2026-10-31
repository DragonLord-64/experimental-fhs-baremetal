# Bifrost environment patch checks

```bash
python3 -m unittest discover -s ops/role-tests/bifrost-environment -v
```

Synthetic checks cover GEN_EMAIL import failures, continued diagnostics after an
import failure, private package snapshots, release constraints, broken/conflicting constraint files, combined three-package
repair and
stopping before further updates after bootstrap failure. Package operations are
mocked; these checks do not establish compatibility with a deployed Kolla image.
