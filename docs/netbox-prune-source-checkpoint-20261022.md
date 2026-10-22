# NetBox prune source checkpoint — 22 October 2026

Source accepted by independent pipeline review netbox-prune-detach-cascade-proof, review attempt 7. Validation in original worker checkout: 73 offline lab tests plus 2 provisioning-isolation tests passed; whitespace passed. Reproduction in this sanitized checkpoint: 73 tests run, 70 pass and 3 importer-specific tests fail because old incidental importer edits are deliberately excluded. These failures are not waived; the separate promoted importer task owns their resolution. Focused prune-source acceptance does not imply this checkpoint passes every inherited importer test. Source preservation only; live pruning is not complete.

Retains raw Collector evidence, stages exact owned address detach operations, requires fresh actual post-detach Collector proof, and protects retained addresses/history and unrelated records. Handles native reverse one-to-one changes during checkpoint resume.

LIVE acceptance pending: authorized private snapshot export, historical-baseline decision, actual detach/Collector proof, independent exact destructive-plan review, and relevant consumer checks. No live inventory writes/deletions occurred. Creation identity was verified only in aggregate; full historical retained baseline is not established. Excludes private snapshots, audit contents, credentials, pipeline logs, binaries and old importer edits. Promoted importer remains separate work in progress.

Checkpoint validation: focused non-importer lab suite 66 passed; provisioning isolation 2 passed; whitespace passed. Entire inherited lab suite: 70 passed, 3 importer-specific failures, all retained and not waived.
