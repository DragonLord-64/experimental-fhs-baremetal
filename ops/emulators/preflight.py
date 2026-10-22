#!/usr/bin/env python3
"""Require measured container headroom before adding emulator pods."""
import subprocess


def main():
    raw = subprocess.check_output(['docker', 'exec', 'fhs-test', 'sh', '-c',
        'cat /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.current; cat /sys/fs/cgroup/memory.stat'], text=True)
    lines = raw.splitlines()
    limit, current = int(lines[0]), int(lines[1])
    stats = dict(line.split() for line in lines[2:])
    working = current - int(stats.get('inactive_file', '0'))
    available = limit - working
    print(f'fhs-test working set {working / 2**20:.1f} MiB / {limit / 2**20:.1f} MiB; available {available / 2**20:.1f} MiB')
    if available < 384 * 2**20:
        raise SystemExit('Need at least 384 MiB measured headroom before emulator deployment; resolve platform capacity first.')

if __name__ == '__main__':
    main()
