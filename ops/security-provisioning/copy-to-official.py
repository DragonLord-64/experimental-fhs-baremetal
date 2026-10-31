#!/usr/bin/env python3
"""Copy provisioning source into the sibling official repository."""
import argparse
from pathlib import Path
import shutil

source = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('destination', nargs='?', type=Path,
                    default=source.parent / 'ska-mid-cbf-fhs-baremetal')
destination = parser.parse_args().destination.resolve()

for name in ('roles', 'playbooks', 'platform', 'docs/src',
             'inventory/dev_env/group_vars/all',
             'inventory/dev_env/group_vars/device_roles_fpga-host-server'):
    shutil.copytree(source / name, destination / name, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'platform-export',
                                                 'platform-secrets.yml', 'platform-endpoints.yml'))
    print(f'Copied {name}/')

for name in ('ansible.cfg', 'inventory/README.md',
             'inventory/dev_env/netbox-inv.yml'):
    target = destination / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / name, target)
    print(f'Copied {name}')

for name in ('setup_fhs_node', 'manage_venvs', 'manage_bittware_sdk',
             'manage_gitlab-runner'):
    old_role = destination / 'roles' / name
    if old_role.exists():
        shutil.rmtree(old_role)
        print(f'Removed roles/{name}/')
    old_role_doc = destination / 'docs/src/roles' / f'{name}.md'
    if old_role_doc.exists():
        old_role_doc.unlink()
        print(f'Removed docs/src/roles/{name}.md')
