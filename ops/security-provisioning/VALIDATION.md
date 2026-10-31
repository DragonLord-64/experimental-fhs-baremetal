# 2026-10-30 validation

Target: existing `fhs-test` cluster on dragonvm. Retained release
`fhs-inventory-alignment` upgraded from revision 6 using current delivered
`platform/charts/fhs-platform`, preserved prior values/PVCs and the existing
scoped renderer. No additional cluster was created. Default context preserved.
Private certificates, credentials, extracted packages and raw logs stay outside
Git in `/home/dragon-lord/fhs-security-20261030`.

Observed:

- Devpi dedicated ingress: verified HTTPS package index; generated action URL
  uses HTTPS; wheel link resolves to the same HTTPS hostname. Downloaded
  `packaging` wheel SHA256 matches the index. The actual `setup_pip_source` role
  rendered a temporary config, then pip installed and imported packaging 26.3
  in a clean virtualenv. Default HTTP and trusted-host inputs both fail before
  writing configuration. Unknown self-signed CA is rejected (curl exit 60).
  Internal backend remains HTTP.
- Squid: HTTPS GitLab `info/refs` returns 200 through HTTP CONNECT, with ordinary
  origin certificate verification. Disallowed `example.com` CONNECT returns 403.
  The actual Git role configured a temporary `GIT_CONFIG_SYSTEM` with
  `http.sslVerify=true`; `git ls-remote` returned upstream HEAD. Current chart
  startup clears stale PID left by a container restart; deployment restart passed.
- APT: Ubuntu noble `InRelease` fetched through actual apt-cacher Service (200).
  This confirms proxy transport, not a fresh device installation/signature check.
- Elasticsearch: retained `elastic` release upgraded with current delivered
  child chart and HTTPS ingress, prior PVC/settings; Kibana disabled lab-only.
- Filebeat: setup-only playbook completes (10 tasks, 0 failures) using official
  9.5.5 `.deb`, separate private setup identity and trusted CA. No Filebeat dpkg
  installation on controller; temporary extraction/configuration removed. Verified
  HTTPS API queries confirm `filebeat-9.5.5` index template and `filebeat` ILM policy
  exist. No setup temporary directories remain.
- Runtime finding corrected in deployment vars: Filebeat HTTPS ingress endpoints
  need explicit `:443`; omitting the port makes Beats attempt port 9200.

- NetBox: dynamic `netbox.netbox.nb_inventory` graph loads using verified HTTPS
  and explicit CA bundle. Current native importers exercised authenticated API,
  chassis create/repeat, serial-preserving rename, compare tasks and FPGA imports
  through the delivered chart ingress. The broader existing acceptance script
  stops at its line 132 ambiguous FPGA identity expectation; this is not recorded
  as a complete importer-suite pass. Parent confirmed related baseline assertions
  separately. No live inventory or hardware was contacted.

The lab uses ClusterIP backends reached through ingress/loopback forwards; it
cannot establish production LoadBalancer automatic DNS integration. Production
uses LoadBalancer Services and site-specific DNS as confirmed by the user.
No production endpoints, hardware provisioning, performance tuning or host
shutdown/reboot operations were exercised.

## Local source checks

- Helm lint passed for default and provisioning values in `hw-management`;
  chart render passed. Existing Grafana coalesce warnings remain.
- Umbrella suite: 10 tests passed. Source-boundary suite: 7 tests passed.
- Provisioning, Filebeat setup, audit and certificate-cleanup syntax passed.
  Inventory inheritance checks preserved the resource layout and site DNS/NTP;
  official runtime pins were retained in the new runtime group-vars file.
- Sphinx HTML built successfully; external intersphinx access was unavailable.
  Changed local source/document links, archive checksums and whitespace passed.
- Existing importer unit suite: 88 tests, four failures and one error. The exact
  five cases also fail on unchanged `4ac9b8c`: two FRU parsing expectations,
  optional FRU discovery fixture, MAC sentinel fixture and Nexus retry fixture
  missing `nexus_parent`. No new failure was introduced by the certificate-default
  change. These are recorded follow-up work, not a passing full-suite claim.

The first local runs could not bind loopback sockets in the sandbox. Rerunning
with network permission allowed the mock HTTP tests; those permission errors are
not counted as application failures. Temporary logs remain under
`/tmp/fhs-security-*.log` on the orchestration host.

## Development HTTP decision — 2026-10-30

Supersedes the HTTPS deployment prerequisites above. The user accepts internal
HTTP on the trusted development LAN and has no assumed control over shared DNS
or ingress. Site values disable dedicated devpi/Elasticsearch ingresses, remove
the proposed hostnames/TLS Secrets, disable shared HTTP-to-HTTPS redirects and
expose Elasticsearch on a LoadBalancer alongside APT/devpi/Git. Existing service
DNS integration must still be verified at the deployment site. Upstream HTTPS
verification and APT package signatures remain enabled.

Observed checks for this revision:

- Helm provisioning lint/render passed. Assertions checked four LoadBalancer
  services/ports, absent dedicated TLS ingresses and no shared TLS/redirect.
  Existing Grafana probe coalesce warnings remain.
- Scoped delivered-chart upgrade passed on existing dragonvm `fhs-test` release
  `fhs-inventory-alignment`, preserving values, credentials and PVCs. Devpi now
  serves HTTP without its prior HTTPS outside URL; NetBox uses HTTP ingress.
- Actual pip role wrote a temporary configuration with the HTTP exception limited
  to the cache host. A fresh venv installed/imported packaging using that config
  through a temporary forward to the real devpi Service.
- Actual setup-only Filebeat playbook passed against the existing lab
  Elasticsearch HTTP Service using the retained 9.5.5 package/private credentials;
  no Filebeat service was installed. Temporary port forwards were stopped.
- Authenticated HTTP NetBox API, dynamic inventory and native manufacturer
  importer check mode passed against the delivered chart. No physical equipment
  was contacted; the importer check did not create the synthetic manufacturer.
- Focused preflight fixture passed HTTP use, unrelated trusted-host rejection,
  HTTPS CA validation/downgrade checks, credential/input failures and unchanged
  input hashes. Preflight/Filebeat syntax and source/link checks passed.
- Sphinx HTML passed with the existing unavailable external-inventory warning.
  Corrected one local role-document link exposed by the build.

Private runtime files/logs remain under
`/home/dragon-lord/fhs-security-20261030/http-check` on dragonvm. These checks do
not establish production DNS, externally assigned LoadBalancer addresses,
network ACLs or the full hardware provisioning/importer suite.

## Shared platform handoff files — 2026-10-30

Ran the actual `platform/charts/export-platform.py` against the existing
`fhs-test` cluster on dragonvm, using release/namespace
`fhs-inventory-alignment`. The scoped release lacks logging, so the fixture
provided a temporary Service/EndpointSlice to the existing Elasticsearch child
chart, temporarily aligned its two unused scoped logging Secret keys, and used
local DNS entries/port forwards to exercise service-domain URLs. All temporary
mappings, forwards and Secret-key changes were restored afterward. This does not
prove the deployment site's external DNS/LoadBalancer integration.

Passed against real chart services:

- Exported the two files, with secrets mode 0600 and no secrets printed.
- Registered the chart's stable legacy NetBox API token; repeat export reused
  exactly the same credentials without rotation.
- Checked DNS/TCP for APT/Git and DNS/TCP plus HTTP responses for NetBox, devpi and
  Elasticsearch, including the standalone endpoint-file checking command.
- Vault-encrypted the entire exported secrets file and loaded real dynamic
  NetBox inventory through the standard plugin's `unvault` token lookup.
- Completed actual Filebeat 9.5.5 setup with the shared encrypted file and real
  Elasticsearch. Fixed the default setup delegate resolution exposed by a clean
  inventory: include-role arguments must default to localhost before role
  defaults are available.
- Resolved the delivered paths/distribution/monitoring vars and rendered the
  real Filebeat publishing template. It contains only the writer password,
  without the setup password or NetBox token.
- Ran the native manufacturer importer in check mode with the two shared files.
  No manufacturer was created and no physical equipment was contacted.

The isolated inventory tooling initially lacked the collection and `pytz`;
selected the installed collection and added the inventory's required `pytz`
runtime dependency to the existing Python requirements file. A fixture initially
expected an FPGA-only group absent from this synthetic inventory; corrected it
to require parsed device-role groups and no inventory parse errors.

Preflight regression cases, Filebeat syntax, source/link and whitespace checks
passed. Disposable copy-script fixture confirmed generated export files are not
transferred with source and obsolete roles are still removed. Sphinx HTML built
with only the existing unavailable external-inventory warning. Private test
files/logs are under `/home/dragon-lord/fhs-security-20261030/export-check`.
