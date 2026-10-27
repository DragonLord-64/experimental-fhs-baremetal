#!/usr/bin/env python3
"""Small C build and inert package fixtures; no hardware or DOCA behavior."""
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
revision = sys.argv[2] if len(sys.argv) > 2 else '1'
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    package = root / 'package'
    (package / 'DEBIAN').mkdir(parents=True)
    (package / 'DEBIAN/control').write_text('Package: mft\nVersion: 0.0.1\nArchitecture: all\nMaintainer: FHS fixture <test@example.invalid>\nDescription: INERT test fixture, not NVIDIA MFT\n')
    subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(package), str(out / 'doca.deb')], check=True)
    dpdk = root / 'dpdk-fixture'
    dpdk.mkdir()
    (dpdk / 'meson.build').write_text("project('dpdk-fixture', 'c')\nexecutable('dpdk-testpmd', 'main.c', install: true)\n")
    (dpdk / 'main.c').write_text('int main(void) { return ' + revision + '; }\n')
    with tarfile.open(out / 'dpdk.tar.gz', 'w:gz') as archive:
        archive.add(dpdk, arcname=dpdk.name)
    ark = root / 'arkville-fixture/scripts'
    ark.mkdir(parents=True)
    installer = ark / 'install_arkville.sh'
    installer.write_text('''#!/bin/sh
set -eu
printf 'full installer\\n' >> /tmp/fhs-arkville-attempts
if test -e /tmp/fhs-fail-once; then
  rm /tmp/fhs-fail-once
  exit 42
fi
''')
    installer.chmod(0o755)
    with tarfile.open(out / 'arkville_fixture.tar.gz', 'w:gz') as archive:
        archive.add(ark.parent, arcname=ark.parent.name)
