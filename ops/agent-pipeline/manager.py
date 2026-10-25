#!/usr/bin/env python3
"""Inspect the task queue and existing lab; dispatch one queued task on request."""
import argparse
import json
import subprocess
import sys

import pipeline

SSH = ['ssh', '-F', '/home/dragonlord/.ssh/config', '-o', 'BatchMode=yes',
       '-o', 'ConnectTimeout=5', 'dragonvm']
CLUSTER = 'minikube -p fhs-test kubectl -- --context=fhs-test --request-timeout=20s '


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'dispatch-next', 'lab-status', 'lab-up'])
    args = parser.parse_args()
    if args.action == 'status':
        print(json.dumps(pipeline.scout(), indent=2))
    elif args.action == 'dispatch-next':
        tasks = pipeline.scout()
        queued = sorted((t for t in tasks if t['status'] == 'queued'), key=lambda t: t['created'])
        if not queued:
            print('No queued tasks')
            return
        pipeline.launch(pipeline.task_dir(queued[0]['task']))
        print('Dispatched ' + queued[0]['task'])
    elif args.action == 'lab-status':
        # Fixed read-only commands. No credentials, service restarts or full-stack tests.
        commands = [CLUSTER + 'get nodes', CLUSTER + 'get pods -A',
                    CLUSTER + 'get deployments,statefulsets,services,pvc -A']
        for command in commands:
            subprocess.run([*SSH, command], check=True, timeout=45)
    else:
        # Explicit application lifecycle request; both operating systems remain running.
        command = 'cd /home/dragon-lord/experimental-fhs-baremetal && ./ops/kubernetes/lifecycle.sh up'
        subprocess.run([*SSH, command], check=True, timeout=360)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
