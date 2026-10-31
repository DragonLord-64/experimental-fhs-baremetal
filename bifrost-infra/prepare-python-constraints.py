#!/usr/bin/env python3
"""Preserve the Kolla release constraints, overriding only Python CA fixes."""
import argparse
from pathlib import Path
import re


def prepare(source):
    text = source.read_text()
    names = {re.split(r'[=<>!~;\s]', line.strip(), maxsplit=1)[0].lower()
             for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')}
    if not {'pyopenssl', 'cryptography', 'jwcrypto'}.issubset(names):
        raise ValueError('Use the complete Kolla release upper-constraints file')
    lines = [line for line in text.splitlines()
             if not re.match(r'^\s*(pip|certifi)\s*[=<>!~]', line, re.I)]
    return '\n'.join(lines) + '\npip===26.2.2\ncertifi===2026.10.23\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('/requirements/upper-constraints.txt'))
    parser.add_argument('--output', type=Path, default=Path('/etc/bifrost/python-constraints.txt'))
    args = parser.parse_args()
    data = prepare(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(data)
    print('Saved release constraints with pip/certifi security fixes: ' + str(args.output))
