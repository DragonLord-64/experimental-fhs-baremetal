# Official source review

2026-10-24: official `development2` at
`0658e93b7fa0ebbcdbcb85afcce99b1cbbc45bcd`, compared with experimental
`eee2d6d`. Reviewed file differences and parsed importer YAML; transferred
selected changes, without merging the unrelated snapshot histories.

- Umbrella/chart changes (`b22afc4`, `a514510`, `2c63437`, `71375b5`) are already
  represented. Dependencies, dashboards and non-README chart files match.
- Playbook promotion/archive (`d7f94d6`) is represented by private `50b2cf0`.
- Added missing fleet-MAC exclusions `ee:ee:ee:ee:ee:ee` and `00:00:00:00` to
  guard/read/write filtering. Real Jinja regression covers sentinel handling.
- Retained the official README's user profile: release `mid-cbf-hw`, namespace
  `hw-management`, prefix `/mid-cbf-hw`. Kept candidate/context, static-route and
  media-affinity instructions; corrected URLs follow the selected prefix.

## Older gaps, outside this transfer

These differences predate the latest development2 changes. They need separate
scope and tests; they were not silently copied during Inventory alignment:

- `1753976`: SDK apt-cache flags and DOCA cache-error handling.
- `9305857`: virtualenv pip/ownership behavior.
- `e311d23`: FPGA BMC reconnect polling (12 attempts, five seconds).
- `bc1e629`: exporter enable/start intent; preserve experimental daemon reload
  if transferring this separately.
- `931706d`: site host/tag/CIS path changes and backup-script guards.
- Official `.make` gitlink `dfaa752` is absent from the private snapshot despite
  `.gitmodules`; submodule adoption is separate.

Raw inventory/archive captures were not copied. Official upstream remains
fetch-only here with push URL `/dev/null`. The user transfers accepted private
changes to the official repository separately.
