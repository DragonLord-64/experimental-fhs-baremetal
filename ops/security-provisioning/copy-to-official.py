#!/usr/bin/env python3
"""Copy the current hwmanage changes into the sibling official repository."""
import argparse
from pathlib import Path
import shutil

source = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('destination', nargs='?', type=Path,
                    default=source.parent / 'ska-mid-cbf-fhs-baremetal')
scope = parser.add_mutually_exclusive_group()
scope.add_argument('--full', action='store_true',
                   help='Copy the full provisioning update and perform its legacy cleanup')
scope.add_argument('--bifrost-only', action='store_true',
                   help='Copy only the six Bifrost environment repair/build files')
scope.add_argument('--diagnostics-only', action='store_true',
                   help='Copy the hwmanage application, import diagnostics and usage page')
args = parser.parse_args()
destination = args.destination.resolve()

# Preserve the original executable when upgrading to the application directory.
legacy = destination / 'scripts/hwmanage'
if not args.bifrost_only and legacy.exists() and not legacy.is_dir():
    backup = legacy.with_name('hwmanage.legacy')
    if backup.exists() or backup.is_symlink():
        parser.error('scripts/hwmanage.legacy already exists; preserve the old command before copying')
    legacy.rename(backup)
    print('Preserved scripts/hwmanage as scripts/hwmanage.legacy')

if args.diagnostics_only:
    shutil.copytree(source / 'scripts/hwmanage', destination / 'scripts/hwmanage', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    print('Copied scripts/hwmanage/')
    for name in ('scripts/install-hwmanage.sh', 'bifrost-infra/docker-compose.yml',
                 'playbooks/netbox/netbox_transfer.py',
                 'playbooks/netbox/ironic_import.yml', 'playbooks/netbox/ironic_minimal.py',
                 'docs/src/playbooks/hwmanage.md', 'ansible.cfg',
                 'inventory/dev_env/netbox-inv.yml', 'inventory/dev_env/group_vars/all/paths.yml',
                 'playbooks/netbox/defaults.yml'):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
        print(f'Copied {name}')
    raise SystemExit(0)

if args.bifrost_only:
    for name in ('scripts/patch-bifrost-environment.py',
                 'scripts/deploy-bifrost-container.sh',
                 'bifrost-infra/Dockerfile',
                 'bifrost-infra/prepare-python-constraints.py',
                 'docs/src/bifrost-infra/operations.md',
                 'docs/src/bifrost-infra/QUICKSTART.md'):
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
        print(f'Copied {name}')
    raise SystemExit(0)

# Exact feature manifest: preserve destination roles, site overrides and unrelated docs.
if not args.full:
    directories = (
        'scripts/hwmanage',
        'bifrost-infra/templates',
        'playbooks/netbox',
    )
    files = (
        'platform/deploy.sh',
        'platform/charts/deploy_upgrage_mid-cbf-hw.sh',
        'platform/charts/export-platform.py',
        'platform/README.md',
        'platform/charts/fhs-platform/README.md',
        'scripts/install-hwmanage.sh',
        'bifrost-infra/docker-compose.yml',
        'playbooks/site.yml',
        'playbooks/provision.yml',
        'playbooks/switch-poap/configure_nexus.yml',
        'playbooks/hwmanage_check_hosts.yml',
        'playbooks/hwmanage_wait.yml',
        'inventory/dev_env/hwmanage-vars.yml',
        'inventory/dev_env/netbox-inv.yml',
        'inventory/dev_env/group_vars/all/paths.yml',
        'ansible.cfg',
        'docs/src/playbooks/hwmanage.md',
        'docs/src/playbooks/site.yml.md',
        'docs/src/playbooks/usage.md',
        'docs/src/index.rst',
    )
    for name in directories:
        shutil.copytree(source / name, destination / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        print(f'Copied {name}/')
    for name in files:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
        print(f'Copied {name}')
    raise SystemExit(0)

for name in ('roles', 'playbooks', 'platform', 'docs/src',
             'scripts/hwmanage', 'bifrost-infra/templates',
             'inventory/dev_env/group_vars/all',
             'inventory/dev_env/group_vars/device_roles_fpga-host-server'):
    shutil.copytree(source / name, destination / name, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'platform-export',
                                                 'platform-secrets.yml', 'platform-endpoints.yml'))
    print(f'Copied {name}/')

for name in ('scripts/install-hwmanage.sh', 'bifrost-infra/docker-compose.yml',
             'inventory/dev_env/hwmanage-vars.yml',
             'bifrost-infra/Dockerfile', 'bifrost-infra/prepare-python-constraints.py',
             'scripts/patch-bifrost-environment.py', 'scripts/deploy-bifrost-container.sh', 'ansible.cfg', 'inventory/README.md',
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

for name in ('elasticsearch.yaml', 'grafana.yaml', 'kibana.yaml',
             'netbox-postgresql.yaml', 'netbox-valkey.yaml', 'netbox.yaml',
             'prometheus.yaml', 'telegraf.yaml'):
    old_values = destination / 'platform' / name
    if old_values.exists():
        old_values.unlink()
        print(f'Removed platform/{name}')
