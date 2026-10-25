#!/usr/bin/env python3
"""Archive committed chart baselines, without reading working values or credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
PRIVATE = '8fe1d1788ff87def0824e5dfa9115a02aa3cebeb'
OFFICIAL = '7b0a306b091306534eef9dfa5872e23547387d7e'


def capture(destination):
    destination.mkdir(parents=True, exist_ok=True)
    records=[]
    for label,revision in [('private',PRIVATE),('official',OFFICIAL)]:
        data=subprocess.run(['git','archive','--format=tar',revision,
            'platform/charts/fhs-platform'],
            cwd=ROOT,check=True,capture_output=True).stdout
        name=label+'-platform.tar'
        (destination/name).write_bytes(data)
        records.append({'source':label,'revision':revision,'archive':name,
            'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
    report={'captured_at':datetime.now(timezone.utc).isoformat(),
        'archives':records,'scope':'Committed chart source only; no site values or credentials'}
    (destination/'baseline.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(capture(parser.parse_args().output),indent=2))
