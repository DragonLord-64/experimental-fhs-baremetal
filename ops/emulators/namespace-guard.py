#!/usr/bin/env python3
"""Refuse to adopt or delete a pre-existing namespace without our owner label."""
import json
import subprocess

result=subprocess.run(['minikube','-p','fhs-test','kubectl','--','--context=fhs-test','get','namespace','fhs-emulators','--ignore-not-found','-o','json'],capture_output=True,text=True,check=True)
if result.stdout.strip():
    data=json.loads(result.stdout)
    if data['metadata'].get('labels',{}).get('app.kubernetes.io/part-of')!='fhs-emulators':
        raise SystemExit('Existing fhs-emulators namespace lacks our owner label; refusing to adopt/delete it.')
