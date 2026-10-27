#!/usr/bin/env python3
"""Create a deliberately tiny SDK stand-in deb, never a proprietary SDK substitute."""
from pathlib import Path
import subprocess
import sys
import tempfile

out = Path(sys.argv[1]).resolve()
out.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    (root / 'DEBIAN').mkdir()
    (root / 'DEBIAN/control').write_text('Package: fhs-sdk-fixture\nVersion: 1.0\nArchitecture: all\nMaintainer: FHS test <test@example.invalid>\nDescription: SDK wiring fixture only\n')
    sdk = root / 'usr/share/bittware-sdk'
    (sdk / 'scripts').mkdir(parents=True)
    (sdk / 'bin').mkdir()
    (sdk / 'scripts/bw_pip.py').write_text('''import pathlib, sys, sysconfig
assert sys.prefix != sys.base_prefix, "must install into a venv"
site = pathlib.Path(sysconfig.get_path("purelib"))
metadata = site / "fhs_sdk_fixture-1.0.dist-info"
metadata.mkdir(exist_ok=True)
(metadata / "METADATA").write_text("Metadata-Version: 2.1\\nName: fhs-sdk-fixture\\nVersion: 1.0\\n")
entry = pathlib.Path(sys.prefix) / "bin/bw_card_monitor"
entry.write_text("#!/bin/sh\\nprintf 'SDK fixture only\\\\n'\\n")
entry.chmod(0o755)
''')
    wrapper = sdk / 'bin/bw_pip'
    wrapper.write_text('#!/bin/sh\nexec "$VIRTUAL_ENV/bin/python" /usr/share/bittware-sdk/scripts/bw_pip.py "$@"\n')
    wrapper.chmod(0o755)
    subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(root), str(out)], check=True)
