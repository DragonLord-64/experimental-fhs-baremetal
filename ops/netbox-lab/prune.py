"""Offline exact prune plans. Apply requires an independently reviewed snapshot.

Snapshots contain the frozen device/dependency scope, not global tables.
"""
import copy
import hashlib
import json
import re
from inventory import LabError, OWNER, PREFIX, SITE, MARKER, tagged, ident, seed_offset

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


def validate_retained(state, topology, keep):
    """Reviewed original-population evidence, never a baseline made from live drift."""
    canonical = topology.get('retained_snapshot')
    if not isinstance(canonical, dict) or any(t not in canonical for t in TABLES):
        raise LabError('Reviewed original retained snapshot required')
    baseline = normalized(canonical)
    devices = baseline[TABLES[0]]
    if len(devices) != 23 or {r['name'] for r in devices} != keep:
        raise LabError('Canonical retained population mismatch')
    ids = {r['id'] for r in devices}
    ports = baseline[TABLES[1]]
    pids = {r['id'] for r in ports}
    if any(ident(p.get('device')) not in ids for p in ports):
        raise LabError('Canonical retained interface scope mismatch')
    for table in TABLES[2:]:
        if any(r.get('assigned_object_type') != 'dcim.interface' or
               r.get('assigned_object_id') not in pids for r in baseline[table]):
            raise LabError('Canonical retained allocation scope mismatch')
    sources = {PREFIX + r['name'].lower(): (kind, r)
               for key, kind in [('hosts', 'fhs'), ('switches', 'switch')]
               for r in topology[key]}
    for row in devices:
        fields = row.get('custom_fields', {}).get('fhs_lab') or {}
        kind, source = sources[row['name']]
        if (not all(tagged(row, tag) for tag in (OWNER, 'lab-logical', 'simulated-hardware'))
                or tagged(row, 'lab-provisioning') or row.get('site', {}).get('slug') != SITE
                or row.get('status', {}).get('value') != 'active'
                or fields.get('kind') != 'logical'
                or fields.get('canonical_name', '').lower() != source['name'].lower()
                or fields.get('unit', '').lower() != source.get('unit', '').lower()
                or 'serial' not in row):
            raise LabError('Invalid canonical retained identity/ownership')
        for name, pointer, address in (
                ('mgmt0', 'primary_ip4', source.get('management_ip')),
                ('bmc0', 'oob_ip', '203.0.113.' + str(seed_offset(kind, source, None)))):
            selected = [p for p in ports if ident(p['device']) == row['id'] and p.get('name') == name]
            if len(selected) != 1:
                raise LabError('Canonical retained management/BMC interface missing')
            port = selected[0]
            ip = [r for r in baseline[TABLES[2]] if r['id'] == ident(row.get(pointer))]
            mac = [r for r in baseline[TABLES[3]] if r['id'] == ident(port.get('primary_mac_address'))]
            expected_mac = (source.get('chassis_mac') if name == 'mgmt0' else
                            '02:fb:00:%02x:%02x:00' % (seed_offset(kind, source, None) >> 8,
                                                     seed_offset(kind, source, None) & 255))
            if (not tagged(port, OWNER) or port.get('description') != MARKER
                    or port.get('mgmt_only') is not (name == 'bmc0') or port.get('enabled') is not True
                    or len(ip) != 1 or len(mac) != 1 or not address or not expected_mac
                    or ip[0].get('address') != address + '/32'
                    or not tagged(ip[0], OWNER) or ip[0].get('description') != MARKER
                    or mac[0].get('description') != MARKER
                    or mac[0].get('mac_address', '').lower() != expected_mac.lower()
                    or any(r.get('assigned_object_id') != port['id'] for r in ip + mac)):
                raise LabError('Canonical retained management/BMC defaults invalid')
    actual = {TABLES[0]: [r for r in state[TABLES[0]] if r['name'] in keep],
              TABLES[1]: [r for r in state[TABLES[1]] if ident(r.get('device')) in ids]}
    for table in TABLES[2:]:
        frozen_ids = {r['id'] for r in baseline[table]}
        actual[table] = [r for r in state[table] if r['id'] in frozen_ids or
                         (r.get('assigned_object_type') == 'dcim.interface' and
                          r.get('assigned_object_id') in pids)]
    if safety_projection(normalized(actual)) != safety_projection(baseline):
        raise LabError('Retained canonical identity/default mismatch; no repairs allowed')


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
    validate_retained(state, topology, keep)
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
    if (evidence.get('complete') is not True or evidence.get('device_ids') != sorted(ids)
                or evidence.get('blockers') != []):
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
    # Review: an owned-looking interface may still belong to physical hardware.
    if any(ident(row.get('module')) is not None for row in ports):
        raise LabError('Physical module interface must be preserved')
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
    if evidence.get('facts_sha256') != digest(safety_projection(state)):
        raise LabError('Collector facts binding mismatch')
    validate_collector(evidence, devices, ports, ips, macs, detach_only=True)
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
    # Review: addresses are historical allocations, never disposable orphans.
    for table, rows in ((TABLES[2], ips), (TABLES[3], macs)):
        for row in rows:
            add(table, row, 'PATCH', {'assigned_object_type': None, 'assigned_object_id': None})
    for table, rows in ((TABLES[1], ports), (TABLES[0], devices)):
        for row in rows:
            add(table, row, 'DELETE')
    frozen = {table: {'ids': [r['id'] for r in rows], 'count': len(rows),
                      'sha256': digest(rows)}
              for table, rows in zip(TABLES, (devices, ports, ips, macs))}
    result = {'version': 4, 'frozen': frozen, 'initial': state, 'retained': sorted(keep), 'operations': operations,
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


def safety_projection(snapshot):
    """Compare stored facts, not serializer presentation or mutation timestamps.

    Unknown fields remain checked. Related object summaries are represented by
    their immutable ID; the full scoped records still check their stored facts.
    Assignment summaries duplicate the type/ID and primary-MAC pointers below.
    The approved plan continues to hash the complete original serializer capture.
    """
    presentation = {'url', 'display_url', 'display', 'last_updated'}
    relations = {
        TABLES[0]: {'device_type', 'role', 'tenant', 'platform', 'site', 'location',
                    'rack', 'parent_device', 'virtual_chassis', 'cluster',
                    'primary_ip4', 'primary_ip6', 'oob_ip', 'config_template'},
        TABLES[1]: {'device', 'vdcs', 'module', 'parent', 'bridge', 'lag',
                    'untagged_vlan', 'tagged_vlans', 'vrf', 'vlan_translation_policy',
                    'primary_mac_address', 'cable', 'link_peers', 'connected_endpoints'},
        TABLES[2]: {'vrf', 'tenant', 'nat_inside', 'nat_outside'},
        TABLES[3]: set(),
    }
    def reference(value):
        if isinstance(value, dict) and 'id' in value:
            return {'id': value['id']}
        if isinstance(value, list):
            return [reference(item) for item in value]
        return value
    result = copy.deepcopy(snapshot)
    result.pop('dependency_evidence', None)
    for table in TABLES:
        for row in result[table]:
            # Review: only these known computed fields are excluded. Ownership,
            # serials, custom fields, address/VRF and unknown fields stay frozen.
            ignored = presentation | ({'assigned_object'} if table in TABLES[2:] else set())
            if table == TABLES[0]:
                ignored |= {'primary_ip', 'interface_count'}
            if table == TABLES[1]:
                ignored |= {'mac_address', 'mac_addresses', 'count_ipaddresses'}
            for field in ignored:
                row.pop(field, None)
            for field in relations[table] & row.keys():
                row[field] = reference(row[field])
    return result


def apply(api, provider, approved_plan, approved_sha256, checkpoint=None, batch_size=25):
    """Provider refreshes frozen scope once before and after each bounded batch.

    Exact prefix reconciliation handles a write whose response was lost. A
    checkpoint is advisory: fresh scoped evidence always decides resume position.
    """
    if type(batch_size) is not int or not 1 <= batch_size <= 100:
        raise LabError('Batch size must be 1..100')
    body = {k: v for k, v in approved_plan.items() if k != 'sha256'}
    if digest(body) != approved_sha256 or approved_plan.get('sha256') != approved_sha256:
        raise LabError('Exact parent-approved plan hash required')
    import pathlib
    path = pathlib.Path(checkpoint) if checkpoint else None
    if path and path.exists() and json.loads(path.read_text())['sha256'] != approved_sha256:
        raise LabError('Checkpoint belongs to another plan')
    detach_end = next((i for i, op in enumerate(approved_plan['operations'])
                       if op['method'] == 'DELETE'), len(approved_plan['operations']))
    def position(current):
        evidence = current.pop('dependency_evidence', {})
        state = normalized(approved_plan['initial'])
        state.pop('dependency_evidence', None)
        remaining = [r for r in current[TABLES[0]]
                     if r['id'] in approved_plan['frozen'][TABLES[0]]['ids']]
        ids = {r['id'] for r in remaining}
        ports = [r for r in current[TABLES[1]] if ident(r['device']) in ids]
        pids = {r['id'] for r in ports}
        related = [[r for r in current[t] if r.get('assigned_object_id') in pids
                    and r.get('assigned_object_type') == 'dcim.interface'] for t in TABLES[2:]]
        if (evidence.get('complete') is not True or evidence.get('device_ids') != sorted(ids)
                or evidence.get('blockers') != []):
            raise LabError('Fresh scoped collector evidence required')
        # Review: raw generic-relation cascades authorize detach staging only.
        # A capture bound to current facts must prove zero address effects before DELETE.
        if evidence.get('facts_sha256') != digest(safety_projection(current)):
            raise LabError('Collector facts binding mismatch')
        validate_collector(evidence, remaining, ports, *related, detach_only=True)
        live_parents = {(model, row['id']) for model, rows in zip(MODELS[:2], (remaining, ports)) for row in rows}
        frozen_effects = approved_plan['initial']['dependency_evidence']['effects']
        expected_effects = [effect for effect in frozen_effects
                            if effect['model'] not in MODELS[2:] and ((effect['model'], effect['id']) in live_parents or
                            (effect.get('parent_model'), effect.get('parent_id')) in live_parents)]
        if sorted([e for e in evidence['effects'] if e['model'] not in MODELS[2:]], key=lambda e: (e['model'], e['id'])) != sorted(
                expected_effects, key=lambda e: (e['model'], e['id'])):
            raise LabError('Stale collector identities; stop prune')
        current = safety_projection(current)
        state = safety_projection(state)
        found = 0 if current == state else None
        for i, op in enumerate(approved_plan['operations'], 1):
            # Review: this private comparison state needs no per-operation deep copy.
            rows = state[op['table']]
            row = next(r for r in rows if r['id'] == op['id'])
            if op['method'] == 'DELETE':
                rows.remove(row)
            else:
                # Review: reconcile only the frozen reverse OneToOne induced by
                # this approved forward detach. Unknown/unrelated facts stay fixed.
                targets = ({'primary_mac_address': TABLES[3]} if op['table'] == TABLES[1]
                           else {field: TABLES[2] for field in ('primary_ip4', 'primary_ip6', 'oob_ip')}
                           if op['table'] == TABLES[0] else {})
                for field, table in targets.items():
                    if field not in op['data'] or op['data'][field] is not None:
                        continue
                    old_id = ident(row.get(field))
                    for target in state[table]:
                        if target['id'] != old_id:
                            continue
                        for accessor, relation in target.get('_prune_reverse_one_to_one', {}).items():
                            if relation == {'model': MODELS[TABLES.index(op['table'])], 'field': field}:
                                if ident(target.get(accessor)) != row['id']:
                                    raise LabError('Inconsistent native primary reverse reference')
                                target[accessor] = None
                row.update(copy.deepcopy(op['data']))
            if current == state:
                found = i
        if found is None:
            raise LabError('Stale prune plan; no writes allowed')
        if found >= detach_end:
            validate_collector(evidence, remaining, ports, *related)
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
        # Never cross from disassociation into deletion on pre-detach evidence.
        if index < detach_end:
            end = min(end, detach_end)
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


def validate_collector(evidence, devices, ports, ips, macs, detach_only=False):
    effects = evidence.get('effects')
    if effects is None:
        raise LabError('Explicit collector effects required')
    expected = {(model, row['id']) for model, rows in zip(MODELS, (devices, ports, ips, macs))
                for row in rows}
    seen = set()
    for effect in effects:
        key = (effect.get('model'), effect.get('id'))
        auxiliary = (key[0] == 'extras.taggeditem'
                     and (effect.get('parent_model'), effect.get('parent_id')) in expected
                     and effect.get('parent_model') in MODELS[:2]
                     and effect.get('tag') in {OWNER, 'lab-logical', 'simulated-hardware'})
        if ((not auxiliary and (key not in expected or key[0] not in (MODELS if detach_only else MODELS[:2])))
                or effect.get('owned') is not True or key in seen):
            raise LabError('Unexpected or unowned collector effect')
        seen.add(key)
    required = {(model, row['id']) for model, rows in zip(MODELS[:2], (devices, ports)) for row in rows}
    if not required <= seen:
        raise LabError('Incomplete cascade')
    for update in evidence.get('updates', []):
        if ((update.get('model'), update.get('id')) not in expected
                or update.get('null') is not True
                or update.get('field') not in {
                    'dcim.device': ('primary_ip4', 'primary_ip6', 'oob_ip'),
                    'dcim.interface': ('primary_mac_address',),
                    'ipam.ipaddress': ('assigned_object_id', 'assigned_object_type'),
                    'dcim.macaddress': ('assigned_object_id', 'assigned_object_type'),
                }.get(update.get('model'), ())):
            raise LabError('Unexpected collector field update')
    payload = {k: v for k, v in evidence.items() if k != 'sha256'}
    if evidence.get('sha256') != digest(payload):
        raise LabError('Collector evidence hash mismatch')


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Offline exact scoped prune plan; no network access')
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--topology', type=Path, required=True, help='Reviewed canonical reduced JSON')
    parser.add_argument('--retained-snapshot', type=Path, required=True,
                        help='Independently reviewed original full-population retained facts')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scope-output', type=Path, help='Frozen read scope for every subsequent collector refresh')
    args = parser.parse_args()
    topology = json.loads(args.topology.read_text())
    topology['retained_snapshot'] = json.loads(args.retained_snapshot.read_text())
    result = plan(json.loads(args.snapshot.read_text()), topology)
    if args.scope_output:
        scope = {table: [row['id'] for row in result['initial'][table]] for table in TABLES}
        import os
        fd = os.open(args.scope_output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(scope, stream, sort_keys=True, indent=2)
    import os
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)


if __name__ == '__main__':
    main()
