#!/usr/bin/env python3
"""Run inside disposable fixture container; never against production hosts."""
import grp
import pathlib
import pwd
import subprocess
import sys

expected = int(sys.argv[1])
for user in ['alice', 'bob', 'ubuntu', 'gitlab-runner']:
    record = pwd.getpwnam(user)
    env = pathlib.Path(record.pw_dir) / '.bw_venv'
    assert env.stat().st_uid == record.pw_uid, (user, 'venv owner')
    assert (env / 'fixture-install-count').stat().st_uid == record.pw_uid
    assert int((env / 'fixture-install-count').read_text()) == expected, user
    subprocess.run([str(env / 'bin/python'), '-m', 'pip', 'check'], check=True)
    subprocess.run([str(env / 'bin/bw_card_monitor')], check=True)
    assert (env / '.fhs-bittware-version').read_text().strip() == f'fhs-sdk-fixture=1.{expected - 1} /usr/share/bittware-sdk'
    assert user in grp.getgrnam('bittware').gr_mem
    print('PASS environment', user)
shared = pathlib.Path('/opt/venvs/fhs')
assert shared.stat().st_uid == pwd.getpwnam('ubuntu').pw_uid
assert shared.stat().st_gid == grp.getgrnam('bittware').gr_gid
assert shared.stat().st_mode & 0o777 == 0o750
assert int((shared / 'fixture-install-count').read_text()) == expected
assert (shared / '.fhs-bittware-version').read_text().strip() == f'fhs-sdk-fixture=1.{expected - 1} /usr/share/bittware-sdk'
subprocess.run([str(shared / 'bin/python'), '-m', 'pip', 'check'], check=True)
subprocess.run([str(shared / 'bin/bw_card_monitor')], check=True)
for user in ['alice', 'ubuntu']:
    assert user in grp.getgrnam('preserved').gr_mem
assert 'gitlab-runner' not in grp.getgrnam('sudo').gr_mem
assert pwd.getpwnam('gitlab-runner').pw_uid < 1000
assert '/home/alice' != pwd.getpwnam('gitlab-runner').pw_dir
print('PASS shared permissions, preserved groups, ordinary runner isolation')
