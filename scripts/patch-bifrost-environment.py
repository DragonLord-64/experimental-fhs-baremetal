#!/usr/bin/env python3
"""Diagnose or patch the running Bifrost container's Kolla Python environment."""
import argparse
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import subprocess
import sys

# Published by the Python security team; the hash authenticates the bootstrap wheel.
# https://discuss.python.org/t/109576
PIP_WHEEL = (
    'https://files.pythonhosted.org/packages/3f/06/'
    '3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/'
    'pip-26.2.2-py3-none-any.whl#sha256='
    'fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'
)
METADATA = '''
import json, sys
from importlib.metadata import distribution, distributions, version
names = {d.metadata['Name'] for d in distributions() if d.metadata['Name']}
# version(name) uses Python's active search precedence, unlike a last-wins dict.
packages = {name: version(name) for name in names}
locations = {name: str(distribution(name).locate_file('')) for name in names
             if name.lower() in ('pip', 'certifi', 'pyopenssl', 'cryptography', 'ironic')}
print(json.dumps({'python': sys.version, 'executable': sys.executable,
                  'packages': packages, 'locations': locations}, indent=2, sort_keys=True))
'''
IMPORTS = '''
import importlib, sys
from importlib.metadata import distribution
failed = False
for name in ('OpenSSL.crypto', 'eventlet', 'oslo_service.backend'):
    try:
        importlib.import_module(name)
        print('PASS import ' + name)
    except Exception as exc:
        failed = True
        print('FAIL import ' + name + ': ' + type(exc).__name__ + ': ' + str(exc))
try:
    entry = next(ep for ep in distribution('ironic').entry_points
                 if ep.group == 'console_scripts' and ep.name == 'ironic-dbsync')
    entry.load()  # Import only; never call main() or perform a migration.
    print('PASS ironic-dbsync entry point: ' + entry.value)
except Exception as exc:
    failed = True
    print('FAIL ironic-dbsync entry point: ' + type(exc).__name__ + ': ' + str(exc))
sys.exit(1 if failed else 0)
'''


def run(argv, **kwargs):
    return subprocess.run([str(a) for a in argv], check=True, **kwargs)


def metadata(python):
    return json.loads(run([python, '-c', METADATA], capture_output=True, text=True).stdout)


def select_constraints(explicit=None, candidates=None):
    if explicit is not None:
        if not explicit.is_file():
            raise ValueError('Constraints file unavailable or broken link: ' + str(explicit))
        explicit.read_bytes()  # Fail before any update if unreadable.
        return explicit
    candidates = candidates if candidates is not None else (
        Path('/opt/stack/requirements/upper-constraints.txt'),
        Path('/requirements/upper-constraints.txt'))
    valid = [file for file in candidates if file.is_file()]
    if not valid:
        raise ValueError('No readable local upper-constraints.txt found; supply --constraints FILE. No packages changed.')
    contents = [file.read_bytes() for file in valid]
    if any(content != contents[0] for content in contents[1:]):
        raise ValueError('Local constraints files differ; select the installation file with --constraints FILE. No packages changed.')
    return valid[0]


def diagnose(python):
    info = metadata(python)
    print('Python: ' + info['python'].splitlines()[0], flush=True)
    packages = {k.lower().replace('_', '-'): v for k, v in info['packages'].items()}
    for name in ('pip', 'certifi', 'pyopenssl', 'cryptography', 'jwcrypto', 'eventlet', 'oslo.service', 'ironic'):
        print(name + ': ' + packages.get(name, 'not installed'), flush=True)
    for name, location in sorted(info.get('locations', {}).items()):
        print(name + ' location: ' + location, flush=True)
    print('Release constraints candidates (use the file matching this installation):', flush=True)
    for parent in (Path('/requirements'), Path('/opt/stack/requirements')):
        for file in sorted(parent.glob('*constraints*.txt')):
            if file.is_file():
                print('  ' + str(file), flush=True)
    for file in sorted(Path('/bifrost-base-source').glob('*/requirements/*constraints*.txt')):
        if file.is_file():
            print('  ' + str(file), flush=True)
    failures = 0
    for name, minimum in (('pip', (26, 2, 2)), ('certifi', (2026, 10, 19))):
        actual = tuple(int(n) for n in re.findall(r'\d+', packages.get(name, ''))[:3])
        if actual < minimum:
            print('FAIL security minimum: ' + name + ' >= ' + '.'.join(map(str, minimum)), flush=True)
            failures += 1
    for args in ([python, '-m', 'pip', 'check'], [python, '-c', IMPORTS]):
        failures += subprocess.run([str(a) for a in args]).returncode != 0
    if failures:
        print('Environment checks failed. Do not restart Ironic until imports pass.', flush=True)
    return int(bool(failures))


def snapshot(python, folder):
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = 'packages-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json'
    path = folder / name
    # Versions only; no index URLs, environment credentials or driver_info.
    with open(path, 'x', opener=lambda p, flags: os.open(p, flags, 0o600)) as output:
        json.dump(metadata(python), output, indent=2, sort_keys=True)
    print('Saved package versions: ' + str(path), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('diagnose', 'update', 'repair-openssl', 'configure'))
    parser.add_argument('--python', type=Path, default=Path('/var/lib/kolla/venv/bin/python'))
    parser.add_argument('--snapshot-dir', type=Path, default=Path('/var/tmp/bifrost-environment-patches'))
    parser.add_argument('--constraints', type=Path, help='Local release constraints; repair otherwise checks /opt/stack/requirements and /requirements')
    parser.add_argument('--playbooks', type=Path, default=Path('/bifrost/playbooks'),
                        help='Installed Bifrost playbook directory for configure')
    parser.add_argument('--build-images', action='store_true',
                        help='With configure, retain the image-build settings from mounted target vars')
    args = parser.parse_args()
    if args.build_images and args.action != 'configure':
        parser.error('--build-images is only valid with configure')
    if not args.python.is_file():
        parser.error('Python executable does not exist: ' + str(args.python))
    if args.action == 'repair-openssl':
        try:
            args.constraints = select_constraints(args.constraints)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        print('Using constraints: ' + str(args.constraints), flush=True)
    if args.action == 'diagnose':
        return diagnose(args.python)
    if os.geteuid() != 0:
        parser.error('Run update/repair/configure inside the Bifrost container as root')
    if args.action == 'update' and not Path('/var/lib/kolla/venv/pyvenv.cfg').is_file():
        parser.error('Kolla environment not found; run inside the Bifrost container')
    if args.action == 'configure':
        if diagnose(args.python):
            return 1
        if not (args.playbooks / 'install.yaml').is_file():
            parser.error('Bifrost install.yaml not found under --playbooks')
        # Preserve the running Ironic version; configuration is not an upgrade.
        env = dict(os.environ, VENV=str(args.python.parent.parent), OS_CLOUD='')
        command = [args.python.parent / 'ansible-playbook', '-i', 'inventory/target', 'install.yaml',
                   '-e', 'skip_install=true', '-e', 'skip_package_install=true',
                   '-e', 'update_repos=false']
        if not args.build_images:
            command += ['-e', 'create_image_via_dib=false', '-e', 'create_ipa_image=false',
                        '-e', 'download_ipa=false']
        run(command, cwd=args.playbooks, env=env)
        return diagnose(args.python)
    snapshot(args.python, args.snapshot_dir)
    if args.action == 'update':
        run(['apt-get', 'update'])
        run(['apt-get', 'install', '-y', 'ca-certificates'])
        run(['update-ca-certificates'])
        # Isolated mode avoids the site's HTTP pip index / trusted-host settings.
        run([args.python, '-m', 'pip', '--isolated', 'install', '--no-cache-dir',
             '--no-deps', '--upgrade', 'pip @ ' + PIP_WHEEL])
        run([args.python, '-m', 'pip', '--isolated', 'install', '--no-cache-dir',
             '--index-url', 'https://pypi.org/simple', '--upgrade', 'certifi>=2026.10.19'])
    else:
        # A separate, deliberate repair: do not guess compatible OpenStack versions.
        run([args.python, '-m', 'pip', '--isolated', 'install', '--no-cache-dir',
             '--index-url', 'https://pypi.org/simple', '--constraint', args.constraints,
             '--upgrade', 'pyOpenSSL', 'cryptography', 'jwcrypto'])
    print('No services restarted. This does not patch IPA, OS images or other virtualenvs.', flush=True)
    return diagnose(args.python)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print('Stopped: command failed with exit code ' + str(exc.returncode), file=sys.stderr)
        sys.exit(exc.returncode)
