# setup_pip_source container baseline

[Preserved screen evidence](VALIDATION.md). This screen changes the harness only.

Shared local/CI entry point, using the pinned `tests/molecule/requirements*`
toolchain and collections in an isolated environment:

```sh
PATH=/tmp/fhs-molecule-venv/bin:$PATH \
FHS_TEST_COLLECTIONS=/home/dragon-lord/fhs-molecule-work/build/molecule-collections \
bash scripts/test-setup-pip-source.sh --baseline
```

Worker Docker access is prohibited for this run. The exact command and source
hashes are submitted in ignored `.pipeline-bridge/request.json`; only a matching
supervisor response and actual logs establish live results.

The baseline performs fresh convergence of the actual role, exact pip.conf
content/metadata and canary checks, strict Molecule idempotence, and owned cleanup.
The play mirrors `playbooks/site.yml` dynamic `include_role` and `apply` tag
inheritance. Original production tags remain intact for baseline comparison.
One uniquely labelled container has 512 MiB, one CPU and 128 PIDs; no mounts,
published ports, devices, host networking or privilege are requested. The pinned
Ubuntu image is pulled with a 180-second timeout; lifecycle timeout is 900 seconds.
Only the disposable container receives Python and `/etc/pip.conf` changes.
Fixture URLs use `.invalid`; pip does not contact them.

Reports: ignored `build/reports/molecule/setup-pip-source-baseline/<unique-name>/`
contains versions, lifecycle output, cleanup and remaining-container evidence.
Retain failures too. This is container userland evidence, with no hardware claims.

Implementation still needs full changed-input, observed corruption/repair,
zero-change recovery rerun, empty-input preservation, broader unrelated-file
checks, effective network/device isolation assertions, failure-path cleanup proof,
and original-versus-minimal tag selection/state comparison (including dynamic
`apply` inheritance). Do not infer these from the baseline. Extend this entry
point for full acceptance and keep final reports separate. Production fixes
require demonstrated baseline failure; tags require justified selection evidence.
