#!/usr/bin/env python3
"""Fast source checks; no deployments, package installs or model calls."""
import argparse
import ast
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]


def check(paths):
    failures = []
    checked = 0
    for name in sorted(set(paths)):
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            if path.suffix == '.py':
                ast.parse(path.read_bytes(), filename=name)
            elif path.suffix == '.json':
                json.loads(path.read_text())
            elif path.suffix == '.sh':
                subprocess.run(['bash', '-n', str(path)], check=True, capture_output=True, text=True)
            elif path.suffix == '.md':
                source = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
                for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)\s]+)\)', source):
                    target = target.split('#')[0]
                    if not target or ':' in target or target.startswith(('/', '$', '<')):
                        continue
                    if not (path.parent / unquote(target)).exists():
                        failures.append(f'{name}: missing relative link {target}')
            else:
                continue
            checked += 1
        except (ValueError, SyntaxError, UnicodeError, subprocess.CalledProcessError) as error:
            failures.append(f'{name}: {getattr(error, "stderr", None) or error}')
    return checked, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all', action='store_true', help='audit every tracked source file')
    parser.add_argument('--base', default='HEAD', help='compare changed files against this Git revision')
    parser.add_argument('paths', nargs='*', help='explicit paths, otherwise changed tracked files')
    args = parser.parse_args()
    if args.paths and args.all:
        parser.error('choose explicit paths or --all')
    if args.all:
        paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    elif args.paths:
        paths = args.paths
    else:
        paths = subprocess.check_output(['git', 'diff', '--name-only', '-z', args.base, '--'], cwd=ROOT).decode().split('\0')
    subprocess.run(['git', 'diff', '--check', args.base, '--', *([] if args.all else [p for p in paths if p])], cwd=ROOT, check=True)
    count, failures = check(paths)
    print(f'{count} source/link checks; {len(failures)} failures')
    for failure in failures:
        print(failure, file=sys.stderr)
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
