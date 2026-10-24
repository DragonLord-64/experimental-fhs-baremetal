#!/usr/bin/env python3
"""Verify immutable sources and record evidence without altering them."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCE=Path('/home/dragon-lord/fhs-pipeline-inputs/dashboard-reference')

def main():
    entries=[]
    for path in sorted(SOURCE.rglob('*')):
        if path.is_file():
            entries.append({'path':str(path.relative_to(SOURCE)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    groups={}
    for item in entries:
        if item['path'].startswith('official/'):
            groups.setdefault(item['sha256'],[]).append(item['path'])
    result={'input_root':str(SOURCE),'note':'Immutable copied working-tree input. HEAD in MANIFEST is provenance, not a claim that dirty input was committed. Original captures remain separate from generated output. Source licensing is retained in the immutable reference storage; generated code follows repository licensing.', 'files':entries, 'official_unique_sources':[{'sha256':sha,'paths':paths} for sha,paths in groups.items()]}
    (ROOT/'PROVENANCE.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
