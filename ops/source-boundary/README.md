# Source boundary checks

[Copy/sync map](../../wiki/source-boundary.md); [immutable relocation manifest](PROVENANCE.json).

```sh
python3 -m unittest discover -s ops/source-boundary -v
```

2026-10-24: six boundary checks pass, including isolated chart rendering,
all six bundled dashboard archives, local image build context, source symlinks,
shared documentation links and the relocated role runner. Docker/Molecule are
stubbed for launcher checks; no container lifecycle or image build is claimed.
Eleven capture/reference hashes and four preserved official-file hashes match.
Original provenance labels remain historical; the manifest records new locations.

Regression results after moves: 47 dashboard tests, 19 static-demo tests,
38 importer alignment tests, ten umbrella tests and 12 controller tests pass.
Shell syntax and `git diff --check` pass. Strict Sphinx 7.4.7
`-E -a -b html -n -W --keep-going` succeeds on a separate dragonvm source copy
with `docs/`, `roles/` and required `bifrost-infra/` includes. Its first run
exposed an unnecessary local private-test link and omitted Bifrost test inputs;
the corrected source/copy passed without suppressing warnings.

Existing GitLab/Read the Docs build paths and pipeline entrypoints did not move.
No services were redeployed, paused runs resumed or physical hardware tested.
The preserved official legacy Molecule scenario/all-role script are not the
validated lab entrypoint; see the copy map for their known historical limits.
