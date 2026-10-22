#!/usr/bin/env python3
"""Bounded synthetic log source and strict Elasticsearch search-result verifier."""
import argparse
import datetime as dt
import json
from pathlib import Path
import re

HOST = 'vccunit1-fhs1'
LEVELS = ((6, 'info', 'Synthetic service ready'),
          (4, 'warning', 'Synthetic service retry'),
          (3, 'error', 'Synthetic service check failed'))


def generate(directory, run, batch):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', run):
        raise ValueError('run must be 1..64 lowercase ASCII letters, digits or hyphens')
    if batch not in (0, 1):
        raise ValueError('only batches 0 and 1 are supported')
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{run}.ndjson'
    if any(other != path for other in directory.glob('*.ndjson')):
        raise ValueError('one run per fixture directory; clean owned resources explicitly')
    # At most six events per run. Exclusive creation prevents accidental replay.
    mode = 'x' if batch == 0 else 'a'
    if batch == 1:
        prior = [json.loads(line) for line in path.read_text().splitlines()]
        if len(prior) != 3 or any(e['event']['id'] != f'{run}-{i}' for i, e in enumerate(prior)):
            raise ValueError('batch 1 requires exactly the original three events')
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    events = []
    for i, (priority, level, message) in enumerate(LEVELS, batch * 3):
        events.append({'@timestamp': now, 'host': {'name': HOST},
                       'service': {'name': 'fhs-synthetic-system'},
                       'process': {'name': 'fhs-log-fixture', 'pid': 1},
                       'event': {'id': f'{run}-{i}', 'dataset': 'fhs.synthetic',
                                 'original': message},
                       'labels': {'test_run': run}, 'message': message,
                       'log': {'syslog': {'priority': priority}}})
    with path.open(mode) as output:
        for event in events:
            output.write(json.dumps(event, separators=(',', ':')) + '\n')
    return path


def verify(source, response, run, count):
    expected = [json.loads(line) for line in source.read_text().splitlines()]
    assert len(expected) == count and count in (3, 6), 'fixture count'
    assert all(e['labels']['test_run'] == run for e in expected), 'fixture run'
    hits = response['hits']
    assert hits['total'] == {'value': count, 'relation': 'eq'}, 'exact total required'
    docs = [h['_source'] for h in hits['hits']]
    assert len(docs) == count, 'truncated search'
    assert len({d['event']['id'] for d in docs}) == count, 'duplicate IDs'
    by_id = {d['event']['id']: d for d in docs}
    assert set(by_id) == {e['event']['id'] for e in expected}, 'event IDs'
    assert {d['host']['name'] for d in docs} == {HOST}, 'one canonical host'
    for event in expected:
        actual = by_id[event['event']['id']]
        for field in ('host', 'service', 'process', 'event', 'labels', 'message'):
            assert actual[field] == event[field], field
        assert actual['log']['syslog']['priority'] == event['log']['syslog']['priority'], 'raw priority'
        assert actual['log']['level'] == dict(LEVELS_BY_PRIORITY)[event['log']['syslog']['priority']], 'level'
        assert dt.datetime.fromisoformat(actual['@timestamp'].replace('Z', '+00:00')) == dt.datetime.fromisoformat(event['@timestamp'].replace('Z', '+00:00')), 'timestamp'
    return {'events': count, 'host': HOST, 'run': run}


LEVELS_BY_PRIORITY = [(priority, level) for priority, level, _ in LEVELS]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    gen = sub.add_parser('generate')
    gen.add_argument('--directory', type=Path, required=True)
    gen.add_argument('--run', required=True)
    gen.add_argument('--batch', type=int, choices=(0, 1), default=0)
    check = sub.add_parser('verify')
    check.add_argument('--source', type=Path, required=True)
    check.add_argument('--response', type=Path, required=True)
    check.add_argument('--run', required=True)
    check.add_argument('--count', type=int, choices=(3, 6), required=True)
    query = sub.add_parser('query')
    query.add_argument('--run', required=True)
    args = parser.parse_args()
    if args.command == 'generate':
        print(generate(args.directory, args.run, args.batch))
    elif args.command == 'verify':
        print(json.dumps(verify(args.source, json.loads(args.response.read_text()), args.run, args.count)))
    else:
        print(json.dumps({'size': 20, 'track_total_hits': True,
                          'query': {'term': {'labels.test_run': args.run}}}))


if __name__ == '__main__':
    main()
