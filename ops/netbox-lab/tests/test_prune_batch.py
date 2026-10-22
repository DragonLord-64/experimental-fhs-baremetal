"""Bounded apply, checkpoint recovery and historical-allocation regressions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_prune import fixture, refresh_evidence
import prune
from inventory import LabError


class BatchTests(unittest.TestCase):
    def test_allocations_are_detached_never_deleted_and_history_is_preserved(self):
        state, topology = fixture()
        state[prune.TABLES[2]][0].update(address='192.0.2.5/24', vrf={'id': 80},
                                      custom_fields={'history': 'keep'}, status='active')
        state[prune.TABLES[3]][0].update(mac_address='02:00:00:00:00:01', comments='history')
        refresh_evidence(state, topology)
        plan = prune.plan(state, topology)
        original = copy.deepcopy(state)
        for op in plan['operations']:
            if op['table'] in prune.TABLES[2:]:
                self.assertEqual(op['method'], 'PATCH')
                self.assertEqual(op['data'], {'assigned_object_type': None, 'assigned_object_id': None})
            state = prune.advance(state, op)
        for table in prune.TABLES[2:]:
            expected = dict(original[table][0], assigned_object_type=None, assigned_object_id=None)
            self.assertEqual(state[table], [expected] + original[table][1:])

    def test_collector_cannot_delete_even_owned_historical_allocations(self):
        for model, table in zip(prune.MODELS[2:], prune.TABLES[2:]):
            state, topology = fixture()
            evidence = state['dependency_evidence']
            evidence['effects'].append({'model': model, 'id': state[table][0]['id'], 'owned': True})
            evidence['sha256'] = prune.digest({k: v for k, v in evidence.items() if k != 'sha256'})
            with self.subTest(model=model), self.assertRaises(LabError):
                prune.validate_collector(
                    evidence, [r for r in state[prune.TABLES[0]] if r['id'] in evidence['device_ids']],
                    [state[prune.TABLES[1]][0]], [state[prune.TABLES[2]][0]], [state[prune.TABLES[3]][0]])

    def test_lost_response_checkpoint_resume_and_completed_empty_scope(self):
        state, topology = fixture()
        plan = prune.plan(state, topology)
        class API:
            calls = 0
            fail = True
            def call(self, path, method, data):
                nonlocal state
                op = plan['operations'][self.calls]
                if (path, method, data) != (f"{op['table']}{op['id']}/", op['method'], op['data']):
                    raise AssertionError('Unexpected operation')
                state = prune.advance(state, op)
                self.calls += 1
                if self.fail and self.calls == 5:
                    raise RuntimeError('Response lost')
        api = API()
        reads = 0
        def provider():
            nonlocal reads
            reads += 1
            fresh = copy.deepcopy(state)
            refresh_evidence(fresh, topology)
            return fresh
        with tempfile.TemporaryDirectory() as folder:
            checkpoint = Path(folder) / 'checkpoint.json'
            with self.assertRaisesRegex(RuntimeError, 'Response lost'):
                prune.apply(api, provider, plan, plan['sha256'], checkpoint, batch_size=10)
            self.assertEqual(json.loads(checkpoint.read_text())['completed'], 5)
            # A stale checkpoint cannot replay a completed write.
            checkpoint.write_text(json.dumps({'sha256': plan['sha256'], 'completed': 0}))
            api.fail = False
            result = prune.apply(api, provider, plan, plan['sha256'], checkpoint, batch_size=50)
            self.assertEqual(result['resumed_at'], 5)
            self.assertEqual(json.loads(checkpoint.read_text())['completed'], len(plan['operations']))
            writes = api.calls
            prune.apply(api, provider, plan, plan['sha256'], checkpoint)
            self.assertEqual(api.calls, writes)
            self.assertLess(reads, 25)  # Reads scale with batches, not devices/writes.

    def test_fresh_stale_ownership_change_after_batch_stops_more_writes(self):
        state, topology = fixture()
        plan = prune.plan(state, topology)
        class API:
            calls = 0
            def call(self, *args):
                nonlocal state
                state = prune.advance(state, plan['operations'][self.calls])
                self.calls += 1
        api = API()
        def provider():
            fresh = copy.deepcopy(state)
            refresh_evidence(fresh, topology)
            if api.calls:
                fresh[prune.TABLES[0]][-1]['tags'] = [{'slug': 'operator-owned'}]
                refresh_evidence(fresh, topology)
            return fresh
        with self.assertRaisesRegex(LabError, 'Stale prune plan'):
            prune.apply(api, provider, plan, plan['sha256'], batch_size=2)
        self.assertEqual(api.calls, 2)

    def test_unchanged_old_collector_evidence_cannot_resume(self):
        state, topology = fixture()
        plan = prune.plan(state, topology)
        for op in plan['operations']:
            state = prune.advance(state, op)
        class API:
            def call(self, *args):
                raise AssertionError('Must not write')
        with self.assertRaisesRegex(LabError, 'Fresh scoped collector'):
            prune.apply(API(), lambda: copy.deepcopy(state), plan, plan['sha256'])

class SerializerProviderTests(unittest.TestCase):
    """Server storage and serializer rendering deliberately do not use advance()."""

    def server(self, failure=None, native=False):
        state, topology = fixture()
        state[prune.TABLES[2]][0].update(address='192.0.2.5/24', vrf={'id': 80},
                                      custom_fields={'history': 'retain'})
        state[prune.TABLES[3]][0].update(mac_address='02:00:00:00:00:01', comments='retain')
        for table in prune.TABLES:
            for row in state[table]:
                row['last_updated'] = 'before'
        if native:
            state[prune.TABLES[0]][0].update(primary_ip6={'id': 3}, oob_ip={'id': 3})
        class Server:
            calls = 0
            def provider(self):
                fresh = copy.deepcopy(state)
                ports = {r['id']: r for r in fresh[prune.TABLES[1]]}
                for row in fresh[prune.TABLES[0]]:
                    row['primary_ip'] = row.get('primary_ip4')
                    row['interface_count'] = sum(p['device']['id'] == row['id'] for p in ports.values())
                for port in ports.values():
                    port['count_ipaddresses'] = sum(r.get('assigned_object_id') == port['id'] for r in fresh[prune.TABLES[2]])
                    port['mac_addresses'] = [r['id'] for r in fresh[prune.TABLES[3]] if r.get('assigned_object_id') == port['id']]
                    port['mac_address'] = '02:00:00:00:00:01' if port.get('primary_mac_address') else None
                    port['device']['display'] = 'server generated summary'
                for table in prune.TABLES[2:]:
                    for row in fresh[table]:
                        row['assigned_object'] = copy.deepcopy(ports.get(row.get('assigned_object_id')))
                if native:
                    # ORM values() reverse OneToOne projection is derived from
                    # stored forward pointers, independently of prune.advance().
                    mac = fresh[prune.TABLES[3]][0]
                    mac['primary_interface'] = next(
                        ({'id': p['id']} for p in ports.values()
                         if (p.get('primary_mac_address') or {}).get('id') == mac['id']), None)
                    mac['_prune_reverse_one_to_one'] = {'primary_interface': {
                        'model': 'dcim.interface', 'field': 'primary_mac_address'}}
                    mac['unrelated_reverse'] = {'id': 987}
                    ip = fresh[prune.TABLES[2]][0]
                    ip['_prune_reverse_one_to_one'] = {}
                    for field in ('primary_ip4', 'primary_ip6', 'oob_ip'):
                        accessor = field + '_for'
                        ip['_prune_reverse_one_to_one'][accessor] = {
                            'model': 'dcim.device', 'field': field}
                        ip[accessor] = next(
                            ({'id': d['id']} for d in fresh[prune.TABLES[0]]
                             if (d.get(field) or {}).get('id') == ip['id']), None)
                    ip['unrelated_reverse'] = {'id': 986}
                refresh_evidence(fresh, topology)
                return fresh
            def call(self, path, method, data):
                table, pk = path.rstrip('/').rsplit('/', 1)
                rows = state[table + '/']
                row = next(r for r in rows if r['id'] == int(pk))
                if method == 'DELETE':
                    rows.remove(row)
                elif method == 'PATCH':
                    row.update(copy.deepcopy(data))
                    row['last_updated'] = 'after'
                else:
                    raise AssertionError(method)
                self.calls += 1
                if self.calls == failure:
                    raise RuntimeError('response lost after storage commit')
        server = Server()
        return server, state, prune.plan(server.provider(), topology)

    def test_realistic_serializer_successful_batches(self):
        server, state, plan = self.server()
        result = prune.apply(server, server.provider, plan, plan['sha256'], batch_size=2)
        self.assertEqual(result['completed'], len(plan['operations']))
        self.assertEqual(len(state[prune.TABLES[0]]), 23)
        self.assertEqual(state[prune.TABLES[2]][0]['vrf'], {'id': 80})
        self.assertEqual(state[prune.TABLES[2]][0]['custom_fields'], {'history': 'retain'})
        self.assertEqual(state[prune.TABLES[3]][0]['comments'], 'retain')
        writes = server.calls
        prune.apply(server, server.provider, plan, plan['sha256'])
        self.assertEqual(server.calls, writes)

    def test_realistic_serializer_lost_response_recovers_patch_and_delete(self):
        for failure in (3, 5):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                server, state, plan = self.server(failure)
                checkpoint = Path(folder) / 'checkpoint.json'
                with self.assertRaisesRegex(RuntimeError, 'response lost'):
                    prune.apply(server, server.provider, plan, plan['sha256'], checkpoint, batch_size=10)
                self.assertEqual(json.loads(checkpoint.read_text())['completed'], failure)
                result = prune.apply(server, server.provider, plan, plan['sha256'], checkpoint)
                self.assertEqual(result['resumed_at'], failure)
                self.assertEqual(server.calls, len(plan['operations']))

    def test_native_reverse_detach_batches_and_lost_response_resume(self):
        for failure in (None, 1, 2):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                server, state, plan = self.server(failure, native=True)
                checkpoint = Path(folder) / 'checkpoint.json'
                if failure:
                    with self.assertRaisesRegex(RuntimeError, 'response lost'):
                        prune.apply(server, server.provider, plan, plan['sha256'], checkpoint, batch_size=2)
                    self.assertEqual(json.loads(checkpoint.read_text())['completed'], failure)
                result = prune.apply(server, server.provider, plan, plan['sha256'], checkpoint, batch_size=2)
                self.assertEqual(result['resumed_at'], failure or 0)
                self.assertEqual(server.provider()[prune.TABLES[3]][0]['primary_interface'], None)
                self.assertEqual(server.provider()[prune.TABLES[3]][0]['unrelated_reverse'], {'id': 987})
                for field in ('primary_ip4', 'primary_ip6', 'oob_ip'):
                    self.assertIsNone(server.provider()[prune.TABLES[2]][0][field + '_for'])
                self.assertEqual(server.provider()[prune.TABLES[2]][0]['unrelated_reverse'], {'id': 986})
                self.assertEqual(server.calls, len(plan['operations']))
                prune.apply(server, server.provider, plan, plan['sha256'], checkpoint)
                self.assertEqual(server.calls, len(plan['operations']))

    def test_native_reverse_unknown_drift_stops_after_detach(self):
        server, state, plan = self.server(native=True)
        def provider():
            fresh = server.provider()
            if server.calls:
                fresh[prune.TABLES[3]][0]['unrelated_reverse'] = None
            return fresh
        with self.assertRaises(LabError):
            prune.apply(server, provider, plan, plan['sha256'], batch_size=2)
        self.assertEqual(server.calls, 2)

    def test_native_ip_reverse_unrelated_drift_stops_after_detach(self):
        server, state, plan = self.server(native=True)
        def provider():
            fresh = server.provider()
            if server.calls:
                fresh[prune.TABLES[2]][0]['unrelated_reverse'] = None
            return fresh
        with self.assertRaises(LabError):
            prune.apply(server, provider, plan, plan['sha256'], batch_size=1)
        self.assertEqual(server.calls, 1)

    def test_projection_keeps_safety_facts_and_unknown_fields(self):
        server, state, plan = self.server()
        for table, field, value in (
                (prune.TABLES[0], 'serial', 'changed'),
                (prune.TABLES[0], 'created', 'changed'),
                (prune.TABLES[0], 'tags', []),
                (prune.TABLES[1], 'module', {'id': 999}),
                (prune.TABLES[2], 'vrf', {'id': 81}),
                (prune.TABLES[2], 'custom_fields', {'history': 'erased'}),
                (prune.TABLES[3], 'mac_address', '02:00:00:00:00:99'),
                (prune.TABLES[3], 'comments', 'erased'),
                (prune.TABLES[0], 'future_stored_field', 'changed')):
            with self.subTest(table=table, field=field):
                fresh = server.provider()
                fresh[table][0][field] = value
                with self.assertRaises(LabError):
                    prune.apply(server, lambda: copy.deepcopy(fresh), plan, plan['sha256'])
                self.assertEqual(server.calls, 0)
