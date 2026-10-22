"""Run only inside the approved pinned Bifrost image; source inspection only."""
import hashlib
import importlib.metadata
import json
from pathlib import Path

for candidate in ['/bifrost/playbooks/inventory/bifrost_inventory.py', '/bifrost/bifrost/inventory.py']:
    path = Path(candidate)
    if path.is_file():
        source = path.read_text()
        print(json.dumps({'path': candidate, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
        print(source)
    else:
        print(json.dumps({'path': candidate, 'missing': True}))
for group in ['ironic.hardware.types', 'ironic.hardware.interfaces.power',
              'ironic.hardware.interfaces.management', 'ironic.hardware.interfaces.deploy',
              'ironic.hardware.interfaces.boot']:
    print(json.dumps({'entrypoint_group': group, 'fake_entries': [e.name for e in
        importlib.metadata.entry_points(group=group) if 'fake' in e.name]}))
