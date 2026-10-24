#!/usr/bin/env python3
"""Render the validated file inventory as a separate status-only scrape feed."""
import argparse
import json
from pathlib import Path
from exact import visual_hosts


def render():
    lines = ['# HELP fhs_visual_status Visual fixture status, not observed (0=ok).',
             '# TYPE fhs_visual_status gauge']
    lines += ['fhs_visual_status{unit="'+h['unit']+'",fhs="'+h['fhs']+'",origin="visual_fixture"} 0'
              for h in visual_hosts()]
    return '\n'.join(lines)+'\n'


def configmap_patch(snapshot):
    """Offline JSON Patch; supervisor applies only to the inspected lab ConfigMap."""
    meta = snapshot.get('metadata', {})
    if (snapshot.get('kind'), meta.get('namespace'), meta.get('name')) != ('ConfigMap', 'fhs-emulators', 'monitoring-fixtures'):
        raise ValueError('Expected fhs-emulators/monitoring-fixtures ConfigMap')
    if not meta.get('resourceVersion') or not meta.get('uid') or 'node.prom' not in snapshot.get('data', {}):
        raise ValueError('Require live UID/resourceVersion and original node.prom')
    return [
        {'op':'test', 'path':'/metadata/uid', 'value':meta['uid']},
        {'op':'test', 'path':'/metadata/resourceVersion', 'value':meta['resourceVersion']},
        {'op':'add', 'path':'/data/visual-status.prom', 'value':render()},
    ]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--configmap-snapshot', type=Path, help='Render guarded JSON Patch from a supervisor-captured lab ConfigMap; never applies it')
    args = parser.parse_args()
    content=json.dumps(configmap_patch(json.loads(args.configmap_snapshot.read_text())),indent=2)+'\n' if args.configmap_snapshot else render()
    if args.output:
        args.output.write_text(content)
    else:
        print(content, end='')
