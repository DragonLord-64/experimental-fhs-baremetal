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
    refresh_evidence(snapshot, topology)
    return snapshot, topology


def refresh_evidence(state, topology):
    keep = {lab.PREFIX + row['name'] for kind in ('hosts', 'switches') for row in topology[kind]}
    devices = [r for r in state[prune.TABLES[0]] if r['name'] not in keep]
    evidence = {'complete': True, 'device_ids': sorted(r['id'] for r in devices),
                'blockers': [], 'updates': [], 'effects': [
                    {'model': model, 'id': row['id'], 'owned': True}
                    for model, rows in zip(prune.MODELS, (devices, *[state[t] for t in prune.TABLES[1:]]))
                    for row in rows]}
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
        with self.assertRaises(lab.LabError):
            prune.apply(api, lambda: api.state, plan, plan['sha256'])
        api.fail = False
        self.assertEqual(prune.apply(api, lambda: api.state, plan, plan['sha256'])['resumed_at'], 2)
        calls = api.calls
        prune.apply(api, lambda: api.state, plan, plan['sha256'])
        self.assertEqual(api.calls, calls)
        self.assertEqual(len(api.state[prune.TABLES[0]]), 23)
        self.assertTrue(all(not api.state[t] for t in prune.TABLES[1:]))

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
        plan = prune.plan(state, topology)
        self.assertEqual(plan['obsolete_logical'], 160)
        self.assertTrue({op['id'] for op in plan['operations'] if op['table'] == prune.TABLES[0]}.isdisjoint({100, 101, 102, 200}))
