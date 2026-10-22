"""Offline deletion contracts; no network or fixture runtime."""
import copy
import unittest
from test_inventory import lab
import prune


def fixture():
    topology = {'hosts': [], 'switches': []}
    for role, count in [('vcc', 4), ('fsp', 3)]:
        for n in range(1, count + 1):
            topology['switches'].append({'name': f'{role}unit{n}-switch'})
            for h in range(1, 2 if role == 'vcc' else 5):
                topology['hosts'].append({'name': f'{role}unit{n}-fhs{h}'})
    device = {'id': 1, 'name': lab.PREFIX + 'vccunit5-fhs1',
              'site': {'slug': lab.SITE}, 'status': {'value': 'active'},
              'tags': [{'slug': t} for t in (lab.OWNER, 'lab-logical', 'simulated-hardware')],
              'custom_fields': {'fhs_lab': {'kind': 'logical', 'unit': 'VCCUnit5',
                                          'canonical_name': 'vccunit5-fhs1'}},
              'primary_ip4': {'id': 3}}
    port = {'id': 2, 'device': {'id': 1}, 'tags': [{'slug': lab.OWNER}],
            'description': lab.MARKER, 'primary_mac_address': {'id': 4}}
    ip = {'id': 3, 'assigned_object_type': 'dcim.interface', 'assigned_object_id': 2,
          'description': lab.MARKER, 'tags': [{'slug': lab.OWNER}]}
    mac = {'id': 4, 'assigned_object_type': 'dcim.interface', 'assigned_object_id': 2,
           'description': lab.MARKER}
    snapshot = dict(zip(prune.TABLES, [[device], [port], [ip], [mac]]))
    snapshot['dependency_evidence'] = {'complete': True, 'sha256': 'synthetic-only',
                                        'device_ids': [1], 'blockers': []}
    # Full authorized population, with one representative dependency chain.
    for role, count in (('vcc', 24), ('fsp', 27)):
        for unit in range(1, count + 1):
            for suffix in ['switch'] + (['fhs1'] if role == 'vcc' else [f'fhs{n}' for n in range(1, 5)]):
                canonical = f'{role}unit{unit}-{suffix}'
                if lab.PREFIX + canonical == device['name']:
                    continue
                row = copy.deepcopy(device)
                row['id'] = 1000 + len(snapshot[prune.TABLES[0]])
                row['name'] = lab.PREFIX + canonical
                row.pop('primary_ip4')
                row['custom_fields']['fhs_lab'].update(canonical_name=canonical, unit=f'{role}unit{unit}')
                snapshot[prune.TABLES[0]].append(row)
    keep = {lab.PREFIX + r['name']: r for key in ('hosts', 'switches') for r in topology[key]}
    for row in snapshot[prune.TABLES[0]]:
        if row['name'] not in keep:
            continue
        source = keep[row['name']]
        source.update(unit=row['custom_fields']['fhs_lab']['unit'].replace('vccunit', 'VCCUnit').replace('fspunit', 'FSPUnit'),
                      management_ip='192.0.2.' + str(len([r for r in snapshot[prune.TABLES[2]]]) + 1),
                      chassis_mac='02:aa:00:00:%02x:00' % len(snapshot[prune.TABLES[2]]))
        row['serial'] = ''
        kind = 'switch' if source['name'].endswith('switch') else 'fhs'
        offset = lab.seed_offset(kind, source, None)
        for name, pointer, address, mac_address in (
                ('mgmt0', 'primary_ip4', source['management_ip'], source['chassis_mac']),
                ('bmc0', 'oob_ip', '203.0.113.' + str(offset), '02:fb:00:%02x:%02x:00' % (offset >> 8, offset & 255))):
            pk = 10000 + len(snapshot[prune.TABLES[1]])
            snapshot[prune.TABLES[1]].append(dict(port, id=pk, device={'id': row['id']}, name=name,
                enabled=True, mgmt_only=name == 'bmc0', primary_mac_address={'id': pk}))
            snapshot[prune.TABLES[2]].append(dict(ip, id=pk, assigned_object_id=pk, address=address + '/32'))
            snapshot[prune.TABLES[3]].append(dict(mac, id=pk, assigned_object_id=pk, mac_address=mac_address))
            row[pointer] = {'id': pk}
    retained_ids = {r['id'] for r in snapshot[prune.TABLES[0]] if r['name'] in keep}
    retained_ports = {r['id'] for r in snapshot[prune.TABLES[1]] if r['device']['id'] in retained_ids}
    topology['retained_snapshot'] = copy.deepcopy({
        prune.TABLES[0]: [r for r in snapshot[prune.TABLES[0]] if r['id'] in retained_ids],
        prune.TABLES[1]: [r for r in snapshot[prune.TABLES[1]] if r['id'] in retained_ports],
        **{t: [r for r in snapshot[t] if r['assigned_object_id'] in retained_ports] for t in prune.TABLES[2:]}})
    refresh_evidence(snapshot, topology)
    return snapshot, topology


def refresh_evidence(state, topology):
    keep = {lab.PREFIX + row['name'] for kind in ('hosts', 'switches') for row in topology[kind]}
    devices = [r for r in state[prune.TABLES[0]] if r['name'] not in keep]
    evidence = {'complete': True, 'device_ids': sorted(r['id'] for r in devices),
                'blockers': [], 'updates': [], 'effects': [
                    {'model': model, 'id': row['id'], 'owned': True}
                    for model, rows in zip(prune.MODELS[:2], (devices, [r for r in state[prune.TABLES[1]] if r['device']['id'] in {d['id'] for d in devices}]))
                    for row in rows]}
    evidence['facts_sha256'] = prune.digest(prune.safety_projection(prune.normalized(state)))
    evidence['sha256'] = prune.digest(evidence)
    state['dependency_evidence'] = evidence


class PruneTests(unittest.TestCase):
    def test_partial_apply_resume_and_rerun(self):
        snapshot, topology = fixture()
        plan = prune.plan(snapshot, topology)
        class API:
            def __init__(self):
                self.state = copy.deepcopy(snapshot)
                self.calls = 0
                self.fail = True
            def call(self, path, method, data):
                op = plan['operations'][self.calls]
                self.assertion = (path == f"{op['table']}{op['id']}/" and method == op['method'] and data == op['data'])
                if not self.assertion:
                    raise AssertionError('unexpected write')
                self.state = prune.advance(self.state, op)
                self.calls += 1
                if self.fail and self.calls == 2:
                    raise lab.LabError('lost response after write')
        api = API()
        def provider():
            # A real scoped provider recollects dependencies after every batch.
            refresh_evidence(api.state, topology)
            return copy.deepcopy(api.state)
        with self.assertRaises(lab.LabError):
            prune.apply(api, provider, plan, plan['sha256'])
        api.fail = False
        self.assertEqual(prune.apply(api, provider, plan, plan['sha256'])['resumed_at'], 2)
        calls = api.calls
        prune.apply(api, provider, plan, plan['sha256'])
        self.assertEqual(api.calls, calls)
        self.assertEqual(len(api.state[prune.TABLES[0]]), 23)
        self.assertEqual(api.state[prune.TABLES[1]], topology['retained_snapshot'][prune.TABLES[1]])
        for table in prune.TABLES[2:]:
            self.assertEqual(len(api.state[table]), 1 + len(topology['retained_snapshot'][table]))
            self.assertIsNone(api.state[table][0]['assigned_object_id'])
            self.assertIsNone(api.state[table][0]['assigned_object_type'])

    def test_stale_or_unapproved_plan_never_writes(self):
        state, topology = fixture()
        plan = prune.plan(state, topology)
        class API:
            def call(self, *args):
                raise AssertionError('must not write')
        for sha in ('wrong', plan['sha256']):
            changed = copy.deepcopy(state)
            changed[prune.TABLES[0]][0]['name'] += '-changed'
            with self.assertRaises(lab.LabError):
                prune.apply(API(), lambda: changed, plan, sha)

    def test_ambiguous_dependencies_and_archive_rejected(self):
        for mutation in ('port', 'ip', 'mac', 'archive', 'collector', 'external'):
            state, topology = fixture()
            if mutation in ('port', 'ip', 'mac'):
                table = {'port': 1, 'ip': 2, 'mac': 3}[mutation]
                state[prune.TABLES[table]][0]['description'] = 'operator-owned'
            elif mutation == 'archive':
                state[prune.TABLES[0]][0]['status']['value'] = 'offline'
            elif mutation == 'collector':
                state['dependency_evidence']['blockers'] = ['cable']
            else:
                state[prune.TABLES[0]].append({'id': 99, 'name': 'real-target', 'primary_ip4': {'id': 3}})
            with self.subTest(mutation=mutation), self.assertRaises(lab.LabError):
                prune.plan(state, topology)

    def test_provisioning_and_unowned_devices_preserved(self):
        state, topology = fixture()
        for n in range(3):
            state[prune.TABLES[0]].append({'id': 100+n, 'name': lab.PREFIX + f'provision-{n}',
                                         'tags': [{'slug': 'lab-provisioning'}]})
        state[prune.TABLES[0]].append({'id': 200, 'name': 'reachable-ansible-fixture'})
        evidence = state['dependency_evidence']
        evidence['facts_sha256'] = prune.digest(prune.safety_projection(prune.normalized(state)))
        evidence['sha256'] = prune.digest({k: v for k, v in evidence.items() if k != 'sha256'})
        plan = prune.plan(state, topology)
        self.assertEqual(plan['obsolete_logical'], 160)
        self.assertTrue({op['id'] for op in plan['operations'] if op['table'] == prune.TABLES[0]}.isdisjoint({100, 101, 102, 200}))
