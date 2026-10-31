# Bifrost runtime recovery — 2026-10-31

Source failure: repeated install.yaml runs failed at ironic-dbsync while importing
OpenSSL.crypto (`lib.GEN_EMAIL`). The operator had repaired the environment, but
an unrestricted installer run brought the error back.

The cached Kolla 2026.1 image on dragonvm contains Ironic 35.1.1.dev9, pyOpenSSL
24.2.1, cryptography 43.0.3 and jwcrypto 1.5.6. Its Bifrost prep role defaults to
master/source updates, and install.yml reinstalls Ironic from that checkout.
The operator's inspected environment instead reported Ironic 39.1.0.dev114.
Do not replace that live runtime with the older image against its database.

## Focused results

A disposable container used the cached image, no host mounts, dropped capabilities,
no published ports and no conductor/DHCP/PXE services. All DB/API work was local to
that container. Real pip downloads used HTTPS.

- Bootstrapped hash-verified pip 26.2.2 and certifi 2026.10.23.
- Installed incompatible cryptography 50.0.2 + jwcrypto 1.6.1 without dependency
  resolution and reproduced the exact GEN_EMAIL import error.
- Ran repair-openssl against /requirements/upper-constraints.txt. It restored
  cryptography 43.0.3 + jwcrypto 1.5.6; pip check and every import probe passed.
- Created a disposable SQLite schema, obtained HTTP 200 from the real Ironic API
  with an empty node list, and ran the actual ironic-dbsync upgrade successfully.
- Generated the Dockerfile dependency constraints and installed diskimage-builder
  plus ansible-dev-tools with those constraints. A subsequent diagnostic passed
  and retained the working Ironic/OpenSSL dependency set.
- Ran install-guard.yml against the actual delivered Bifrost roles. Source checkout,
  the deliberately impossible pip install and runtime installation all skipped;
  recap changed=0, failed=0. Bootstrap/service/migration tasks were deliberately
  disabled in this fixture; the separate SQLite check covers schema startup.
- Twelve local focused unit checks passed, including configure refusal on failed
  diagnostics, its mandatory skip flags and release-constraint generation.
- Focused transfer copied six files and preserved unrelated role/doc/inventory
  edits, mounted target variables and old-role cleanup candidates.

## Limits

No deployed container, MySQL database, target server, switch or production DHCP
service was changed. The full Dockerfile/system-package build and a full installed
Bifrost configuration run were not executed. This establishes the tested Kolla
base dependency repair, database command startup, constrained Python build steps
and real role skip contracts; it does not establish production database migration
or compatibility with every later Ironic source revision. Complete software
release upgrades and persisted database/configuration migration remain separate.
