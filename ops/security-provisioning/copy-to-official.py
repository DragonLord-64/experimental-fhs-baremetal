#!/usr/bin/env python3
"""Copy reviewed source changes to a sibling official checkout; never commit."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


SOURCE = Path(__file__).resolve().parents[2]
BASE = '2638d5bd1533654bb8edb750fe29e4f4fb47c3b1'
SCOPES = ['roles', 'playbooks', 'platform', 'docs/src', 'ansible.cfg',
          'inventory/README.md', 'inventory/dev_env/netbox-inv.yml',
          'inventory/dev_env/group_vars/all.yml',
          'inventory/dev_env/group_vars/device_roles_fpga-host-server.yml',
          'inventory/dev_env/group_vars/all',
          'inventory/dev_env/group_vars/device_roles_fpga-host-server']
NETBOX = 'inventory/dev_env/netbox-inv.yml'


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', nargs='?', type=Path,
                        default=SOURCE.parent / 'ska-mid-cbf-fhs-baremetal')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination == SOURCE or SOURCE in destination.parents or destination in SOURCE.parents:
        parser.error('Source and destination must be separate checkouts.')
    try:
        top = Path(git(destination, 'rev-parse', '--show-toplevel').strip()).resolve()
        if top != destination:
            parser.error('Destination must be the root of the official Git checkout.')
        if git(destination, 'status', '--porcelain', '--untracked-files=all').strip():
            parser.error('Destination has changes; commit or stash them before copying.')
        names = git(SOURCE, 'diff', '--name-only', '-z', BASE, 'HEAD', '--', *SCOPES).split('\0')
    except subprocess.CalledProcessError as error:
        parser.error(f'Cannot inspect checkouts: {error}')
    paths = [Path(name) for name in names if name]
    if not (destination / NETBOX).is_file():
        parser.error('Destination NetBox inventory is missing; supply its site inventory first.')
    # Reject symlinks before any copy or deletion, including parent directories.
    for relative in paths:
        for root in (SOURCE, destination):
            for part in (relative, *relative.parents):
                if (root / part).is_symlink():
                    parser.error(f'Symlink in transfer path: {root / part}')
        if (destination / relative).is_dir():
            parser.error(f'Expected a file, found a destination directory: {relative}')

    backup = None if args.dry_run else Path(tempfile.mkdtemp(prefix='fhs-transfer-backup-'))
    for relative in paths:
        source, target = SOURCE / relative, destination / relative
        action = 'merge' if str(relative) == NETBOX else ('copy' if source.is_file() else 'delete')
        print(f'{action}: {relative}')
        if args.dry_run:
            continue
        if target.is_file():
            saved = backup / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
        if not source.exists():
            if target.exists():
                target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if str(relative) == NETBOX:
            content = target.read_text()
            # Preserve the destination token/Vault block and inventory filters.
            for key in ('api_endpoint', 'validate_certs'):
                setting = re.search(rf'^{key}:.*$', source.read_text(), re.MULTILINE).group()
                if re.search(rf'^{key}:.*$', content, re.MULTILINE):
                    content = re.sub(rf'^{key}:.*$', lambda match: setting, content, flags=re.MULTILINE)
                else:
                    content += '\n' + setting + '\n'
            target.write_text(content)
        else:
            shutil.copy2(source, target)
    if backup:
        print(f'Original overwritten/deleted files: {backup}')
        print('Copied only. Nothing staged, committed, pushed or deployed in official.')
        print(f'Review: git -C {destination} diff')
        print(f'New files: git -C {destination} status --short')


if __name__ == '__main__':
    main()
