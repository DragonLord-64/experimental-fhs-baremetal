"""Offline exact prune plans. Apply requires an independently reviewed snapshot.

Snapshots contain the frozen device/dependency scope, not global tables.
"""
import copy
import hashlib
import json
import re
from inventory import LabError, OWNER, PREFIX, SITE, MARKER, tagged, ident

TABLES = ('dcim/devices/', 'dcim/interfaces/', 'ipam/ip-addresses/', 'dcim/mac-addresses/')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def normalized(snapshot):
    result = copy.deepcopy(snapshot)
    for table in TABLES:
        rows = result[table]
        if len({r['id'] for r in rows}) != len(rows):
            raise LabError('Duplicate snapshot identity')
        result[table] = sorted(rows, key=lambda r: r['id'])
    return result


def plan(snapshot, topology):
    state = normalized(snapshot)
    # Collector evidence is mandatory: cables, services, modules, VM references,
    # generic relations, etc. cannot be inferred from four REST tables.
    evidence = state.get('dependency_evidence', {})
    if evidence.get('complete') is not True or not evidence.get('sha256'):
        raise LabError('Complete supervisor dependency collector evidence required')
    keep = {PREFIX + r['name'].lower() for k in ('hosts', 'switches') for r in topology[k]}
    expected = {PREFIX + f'vccunit{n}-fhs1' for n in range(1, 5)}
    expected |= {PREFIX + f'fspunit{n}-fhs{h}' for n in range(1, 4) for h in range(1, 5)}
    expected |= {PREFIX + f'{role}unit{n}-switch' for role, count in [('vcc', 4), ('fsp', 3)] for n in range(1, count + 1)}
    if keep != expected:
        raise LabError('Expected exactly 23 retained logical identities')
    devices = []
    for row in state[TABLES[0]]:
        if row['name'] in keep:
            continue
        fields = row.get('custom_fields', {}).get('fhs_lab') or {}
        if (tagged(row, OWNER) and tagged(row, 'lab-logical')
                and not tagged(row, 'lab-provisioning') and tagged(row, 'simulated-hardware')
                and row.get('site', {}).get('slug') == SITE
                and row['name'].startswith(PREFIX) and fields.get('kind') == 'logical'):
            if fields.get('canonical_name', '').lower() != row['name'][len(PREFIX):]:
                raise LabError('Ambiguous logical identity')
            match = re.fullmatch(r'(vcc|fsp)unit([1-9][0-9]*)-(fhs[1-4]|switch)', row['name'][len(PREFIX):])
            if (not match or int(match[2]) > (24 if match[1] == 'vcc' else 27)
                    or (match[1] == 'vcc' and match[3] not in ('fhs1', 'switch'))
                    or fields.get('unit', '').lower() != match[1] + 'unit' + match[2]
                    or row.get('status', {}).get('value') == 'decommissioning'):
                raise LabError('Noncanonical or archived logical identity')
            if row.get('status', {}).get('value') != 'active':
                raise LabError('Only active synthetic logical records may be pruned')
            devices.append(row)
    present = [r['name'] for r in state[TABLES[0]] if r['name'] in keep]
    if len(present) != 23 or set(present) != keep or len(devices) != 160:
        raise LabError('Expected complete 23 retained / 160 obsolete population')
    ids = {r['id'] for r in devices}
    if evidence.get('device_ids') != sorted(ids) or evidence.get('blockers') != []:
        raise LabError('Dependency evidence scope mismatch or blocked deletion')
    ports = [r for r in state[TABLES[1]] if ident(r['device']) in ids]
    pids = {r['id'] for r in ports}
    ips, macs = [], []
    for table, target in ((TABLES[2], ips), (TABLES[3], macs)):
        for row in state[table]:
            if row.get('assigned_object_id') in pids and row.get('assigned_object_type') == 'dcim.interface':
                target.append(row)
    for row in ports + ips:
        if not tagged(row, OWNER) or row.get('description') != MARKER:
            raise LabError('Unowned interface/IP dependency')
    for row in macs:
        if row.get('description') != MARKER:
            raise LabError('Unowned MAC dependency')
    ipids, mids = {r['id'] for r in ips}, {r['id'] for r in macs}
    for row in state[TABLES[0]]:
        if row['id'] not in ids and any(ident(row.get(k)) in ipids for k in ('primary_ip4', 'primary_ip6', 'oob_ip')):
            raise LabError('External primary IP reference')
    for row in state[TABLES[1]]:
        if row['id'] not in pids and ident(row.get('primary_mac_address')) in mids:
            raise LabError('External primary MAC reference')
    validate_collector(evidence, devices, ports, ips, macs)
    operations = []
    def add(table, row, method, data=None):
        operations.append({'table': table, 'id': row['id'], 'method': method, 'data': data})
    for row in devices:
        data = {k: None for k in ('primary_ip4', 'primary_ip6', 'oob_ip') if row.get(k) is not None}
        if data:
            add(TABLES[0], row, 'PATCH', data)
    for row in ports:
        if row.get('primary_mac_address') is not None:
            add(TABLES[1], row, 'PATCH', {'primary_mac_address': None})
    for table, rows in ((TABLES[2], ips), (TABLES[3], macs), (TABLES[1], ports), (TABLES[0], devices)):
        for row in rows:
            add(table, row, 'DELETE')
    result = {'version': 1, 'initial': state, 'retained': sorted(keep), 'operations': operations,
              'obsolete_logical': len(devices), 'topology_sha256': digest(topology)}
    result['sha256'] = digest(result)
    return result


def advance(state, op):
    state = copy.deepcopy(state)
    rows = state[op['table']]
    row = next(r for r in rows if r['id'] == op['id'])
    if op['method'] == 'DELETE':
        rows.remove(row)
    else:
        row.update(op['data'])
    return state


def apply(api, provider, approved_plan, approved_sha256, checkpoint=None, batch_size=25):
    """Provider refreshes frozen scope once before and after each bounded batch.

    Exact prefix reconciliation handles a write whose response was lost. A
    checkpoint is advisory: fresh scoped evidence always decides resume position.
    """
    if not 1 <= batch_size <= 100:
        raise LabError('Batch size must be 1..100')
    body = {k: v for k, v in approved_plan.items() if k != 'sha256'}
    if digest(body) != approved_sha256 or approved_plan.get('sha256') != approved_sha256:
        raise LabError('Exact parent-approved plan hash required')
    import pathlib
    path = pathlib.Path(checkpoint) if checkpoint else None
    if path and path.exists() and json.loads(path.read_text())['sha256'] != approved_sha256:
        raise LabError('Checkpoint belongs to another plan')
    def position(current):
        state = normalized(approved_plan['initial'])
        found = 0 if current == state else None
        for i, op in enumerate(approved_plan['operations'], 1):
            state = advance(state, op)
            if current == state:
                found = i
        if found is None:
            raise LabError('Stale prune plan; no writes allowed')
        return found
    def save(index):
        if path:
            import os
            import tempfile
            fd, temporary = tempfile.mkstemp(dir=path.parent)
            try:
                with os.fdopen(fd, 'w') as stream:
                    json.dump({'sha256': approved_sha256, 'completed': index}, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    start = position(normalized(provider()))
    index = start
    save(index)
    while index < len(approved_plan['operations']):
        if position(normalized(provider())) != index:
            raise LabError('Concurrent change; stop prune')
        end = min(index + batch_size, len(approved_plan['operations']))
        try:
            for op in approved_plan['operations'][index:end]:
                api.call(f"{op['table']}{op['id']}/", op['method'], op['data'])
        except Exception:
            save(position(normalized(provider())))
            raise
        if position(normalized(provider())) != end:
            raise LabError('Unexpected apply result; stop prune')
        index = end
        save(index)
    return {'completed': index, 'resumed_at': start}


MODELS = ('dcim.device', 'dcim.interface', 'ipam.ipaddress', 'dcim.macaddress')


def validate_collector(evidence, devices, ports, ips, macs):
    effects = evidence.get('effects')
    if effects is None:
        raise LabError('Explicit collector effects required')
    expected = {(model, row['id']) for model, rows in zip(MODELS, (devices, ports, ips, macs))
                for row in rows}
    seen = set()
    for effect in effects:
        key = (effect.get('model'), effect.get('id'))
        if key not in expected or effect.get('owned') is not True or key in seen:
            raise LabError('Unexpected or unowned collector effect')
        seen.add(key)
    required = {(model, row['id']) for model, rows in zip(MODELS[:2], (devices, ports)) for row in rows}
    if not required <= seen or evidence.get('updates'):
        raise LabError('Incomplete cascade or unexpected field update')
    payload = {k: v for k, v in evidence.items() if k != 'sha256'}
    if evidence.get('sha256') != digest(payload):
        raise LabError('Collector evidence hash mismatch')


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Offline exact scoped prune plan; no network access')
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--topology', type=Path, required=True, help='Reviewed canonical reduced JSON')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = plan(json.loads(args.snapshot.read_text()), json.loads(args.topology.read_text()))
    import os
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)


if __name__ == '__main__':
    main()
