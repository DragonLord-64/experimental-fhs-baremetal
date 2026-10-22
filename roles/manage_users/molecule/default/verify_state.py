"""Assertions run only inside the disposable container; never print shadow data."""
import grp
import os
from pathlib import Path
import pwd
import spwd
import stat
import subprocess
import sys

# Review note: drift assertions establish the fault before the same role repairs it.
phase = sys.argv[1]
u = pwd.getpwnam("moleculeuser")
key = Path("/home/moleculeuser/.ssh/authorized_keys")
sudo = Path("/etc/sudoers.d/99-fhs-passwordless")
if phase == "drift":
    assert u.pw_shell == "/bin/sh"
    assert key.read_text() == ""
    assert stat.S_IMODE(sudo.stat().st_mode) == 0o600
    sys.exit(0)
# Review note: inspect real identity, shadow, groups, keys and modes inside the disposable container.
assert u.pw_shell == "/bin/bash" and u.pw_dir == "/home/moleculeuser"
assert spwd.getspnam(u.pw_name).sp_pwdp == "$6$rounds=656000$saltysalt$5IbeoxKbjI7g/8oIZjAdULp1WJ4hVTBNRGsTcSlYTOj4nKMfx1l8jH/zsfqHj6zE85cMzNxnEnGqkxbnSpwj/."
for name in ("sudo", "bittware"):
    assert u.pw_name in grp.getgrnam(name).gr_mem
assert "root" in grp.getgrnam("bittware").gr_mem
for path, mode in ((Path(u.pw_dir), 0o750), (key.parent, 0o700), (key, 0o600)):
    s = path.stat()
    assert s.st_uid == u.pw_uid and s.st_gid == u.pw_gid
    assert stat.S_IMODE(s.st_mode) == mode, (str(path), oct(stat.S_IMODE(s.st_mode)))
assert key.read_text().strip() == "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIH/r3rA1qZ8/B8nGRpZGm0XwH/c+jbi+9LWzXJ4z4Cz5 molecule-synthetic"
s = sudo.stat()
assert s.st_uid == 0 and s.st_gid == 0 and stat.S_IMODE(s.st_mode) == 0o440
# Review note: validate both policy contents and sudo's interpretation after convergence.
expected = "%sudo ALL=(ALL) ALL\n" if phase == "changed" else "%sudo ALL=(ALL) NOPASSWD:ALL\n"
assert sudo.read_text() == expected
subprocess.run(["/usr/sbin/visudo", "-cf", "/etc/sudoers"], check=True, capture_output=True)
policy = subprocess.run(["sudo", "-l", "-U", u.pw_name], check=True, capture_output=True, text=True).stdout
assert "(ALL) ALL" in policy if phase == "changed" else "NOPASSWD: ALL" in policy
