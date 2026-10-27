# Nexus management IP — 2026-10-26

The importer now reads `show interface mgmt0` (configurable), observes the
interface name and explicit address/prefix, and uses the shared native NetBox
client to attach the address and select primary IPv4/IPv6. Interface-only import
preserves existing interface type; newly observed interfaces use `other` rather
than guessing a connector. Address ownership is checked before any writes.
Missing/failed/ambiguous observations preserve addresses and primary selection.
No address or prefix comes from the SSH target.

Focused check (covers runtime behavior absent from controller source checks):

```sh
python3 -m unittest discover -s ops/platform/inventory-alignment -p test_nexus_management.py -v
```

Four tests passed: IPv4/IPv6, unchanged repeat, failed/missing/ambiguous reads,
conflicting ownership, preview and interface-only behavior. Uses the existing
stateful REST fixture in `test_importer.py`, with host-IP filter semantics added
only at this test's boundary. [Management output](fixtures/nexus-management/mgmt0.txt)
is synthetic representative NX-OS text; it is not a physical switch capture.

Native lab commands from the local orchestration server:

```sh
ssh -F /home/dragonlord/.ssh/config -o ConnectTimeout=5 dragonvm \
  'minikube -p fhs-test kubectl -- --context=fhs-test get services -n fhs-inventory-alignment'
ssh -F /home/dragonlord/.ssh/config -o ConnectTimeout=5 dragonvm \
  'minikube -p fhs-test kubectl -- --context=fhs-test get pods -n fhs-inventory-alignment'
ssh -F /home/dragonlord/.ssh/config -o ConnectTimeout=5 dragonvm \
  'python3 -' < /tmp/nexus-management-native.py
```

Services inspected before use: retained NetBox, PostgreSQL and Valkey present;
all four pods Running/Ready. No deployment or cluster lifecycle operation.
`helm` was unavailable on PATH; no release-status claim is made from that command.
The temporary native check uses the retained prefixed NetBox service, protected
credentials, and real `ansible-playbook` module packaging. It runs importer
`--syntax-check`, management `--check`, apply and repeat; checks REST interface
ownership, exact prefix and primary IPv4, then closes its temporary port-forward.
Initial run passed all assertions, retaining `SYN-NEXUS-MGMT-1793072810` with
`198.18.255.231/27` on `mgmt0`; private logs on dragonvm:
`/tmp/fhs-nexus-management-check-7ndiw4pt`.

Controller acceptance was not run by this worker. Physical NX-OS access and
other firmware output shapes remain unverified; unsupported shapes diagnose
and preserve existing addressing. No switch configuration changes were made.

After preserving existing interface type and adding management capture/facts
protection, the native check was repeated. Reusing the first retained fixture's
IP stopped at the preview assertion expecting a new plan; the check was corrected
to use a distinct synthetic address. Final native syntax/preview/apply/repeat
passed for `SYN-NEXUS-MGMT-1793072911`, `198.18.255.232/27`; logs:
`/tmp/fhs-nexus-management-check-h4js8y4g`. These small fixture devices remain for
review. No chassis/module/cable lifecycle suite was run.

A final parser correction restricts command-error detection to line starts, so
normal `0 input errors` counters do not suppress management discovery. The four
focused tests passed again with that representative counter line in the fixture.
Additional baseline/parser and final YAML checks (controller does not parse YAML):

```sh
python3 -m unittest discover -s ops/platform/inventory-alignment -p test_discovery.py -k nexus -v
python3 - <<'PY'
import yaml
from pathlib import Path
for name in ['playbooks/netbox/defaults.yml', 'playbooks/netbox/tasks/import_nexus.yml']:
    yaml.safe_load(Path(name).read_text())
    print(name+': YAML parsed')
PY
```

Existing Nexus LLDP parser test passed (1 test); both YAML files parsed. Native
IPv6, actual network-cli discovery, full tagged play execution and physical NX-OS
remain unverified; IPv6 and failure/ownership behavior have focused fixture coverage.
