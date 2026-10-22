"""GenericRelation cascade staging: addresses survive only after disassociation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import prune
from inventory import LabError
from test_prune import fixture, refresh_evidence


def capture(state, topology):
    """Django GenericRelation follows type AND object ID, not primary pointers."""
    fresh = copy.deepcopy(state)
    refresh_evidence(fresh, topology)
    evidence = fresh['dependency_evidence']
    ids = set(evidence['device_ids'])
    ports = {r['id'] for r in fresh[prune.TABLES[1]] if r['device']['id'] in ids}
    for model, table in zip(prune.MODELS[2:], prune.TABLES[2:]):
        for row in fresh[table]:
            if row.get('assigned_object_type') == 'dcim.interface' and row.get('assigned_object_id') in ports:
                evidence['effects'].append({'model': model, 'id': row['id'], 'owned': True})
    evidence['sha256'] = prune.digest({k: v for k, v in evidence.items() if k != 'sha256'})
    return fresh


class DetachTests(unittest.TestCase):
    def server(self):
        state, topology = fixture()
        state[prune.TABLES[2]][0].update(address='192.0.2.9/24', vrf={'id': 71},
                                      custom_fields={'history': 'retain'}, created='original')
        state[prune.TABLES[3]][0].update(mac_address='02:00:00:00:00:ab', created='original')
        original = capture(state, topology)
        plan = prune.plan(original, topology)
        class Server:
            calls = 0
            fail_at = None
            refresh_failure = False
            proofs = []
            def provider(self):
                if self.refresh_failure and self.calls:
                    raise RuntimeError('capture failed')
                fresh = capture(state, topology)
                self.proofs.append(copy.deepcopy(fresh))
                return fresh
            def call(self, path, method, data):
                op = plan['operations'][self.calls]
                if (path, method, data) != (f"{op['table']}{op['id']}/", op['method'], op['data']):
                    raise AssertionError('unexpected operation')
                if method == 'DELETE':
                    # Simulate native generic cascade: deletion would destroy any
                    # still-associated address, irrespective of primary pointers.
                    if any(e['model'] in prune.MODELS[2:] for e in self.proofs[-1]['dependency_evidence']['effects']):
                        raise AssertionError('delete before actual post-detach proof')
                updated = prune.advance(state, op)
                state.clear()
                state.update(updated)
                self.calls += 1
                if self.calls == self.fail_at:
                    raise RuntimeError('lost response')
        return Server(), state, topology, original, plan

    def test_raw_rejected_for_delete_but_exact_staging_preserves_raw_and_allocations(self):
        server, state, topology, raw, plan = self.server()
        evidence = raw['dependency_evidence']
        with self.assertRaises(LabError):
            prune.validate_collector(
                evidence, [r for r in raw[prune.TABLES[0]] if r['id'] in evidence['device_ids']],
                [raw[prune.TABLES[1]][0]], [raw[prune.TABLES[2]][0]], [raw[prune.TABLES[3]][0]])
        self.assertEqual(plan['initial'], prune.normalized(raw))
        prune.apply(server, server.provider, plan, plan['sha256'], batch_size=100)
        for table in prune.TABLES[2:]:
            self.assertEqual(state[table][0], dict(raw[table][0], assigned_object_type=None,
                                                 assigned_object_id=None))
        self.assertTrue(any(not any(e['model'] in prune.MODELS[2:] for e in p['dependency_evidence']['effects'])
                            and len(p[prune.TABLES[0]]) == 183 for p in server.proofs))

    def test_partial_detach_lost_response_resumes_from_fresh_raw_graph(self):
        server, state, topology, raw, plan = self.server()
        server.fail_at = 3  # IP detached; MAC still cascades.
        with tempfile.TemporaryDirectory() as folder:
            checkpoint = Path(folder) / 'checkpoint'
            with self.assertRaisesRegex(RuntimeError, 'lost response'):
                prune.apply(server, server.provider, plan, plan['sha256'], checkpoint, batch_size=100)
            self.assertEqual(json.loads(checkpoint.read_text())['completed'], 3)
            self.assertIsNone(state[prune.TABLES[2]][0]['assigned_object_id'])
            self.assertEqual(state[prune.TABLES[3]][0]['assigned_object_id'], 2)
            server.fail_at = None
            self.assertEqual(prune.apply(server, server.provider, plan, plan['sha256'], checkpoint)['resumed_at'], 3)

    def test_failed_refresh_cannot_cross_boundary_or_trust_checkpoint(self):
        server, state, topology, raw, plan = self.server()
        boundary = next(i for i, op in enumerate(plan['operations']) if op['method'] == 'DELETE')
        for op in plan['operations'][:boundary]:
            state.update(prune.advance(state, op))
        server.calls = boundary
        server.refresh_failure = True
        with tempfile.TemporaryDirectory() as folder:
            checkpoint = Path(folder) / 'checkpoint'
            checkpoint.write_text(json.dumps({'sha256': plan['sha256'], 'completed': boundary}))
            with self.assertRaisesRegex(RuntimeError, 'capture failed'):
                prune.apply(server, server.provider, plan, plan['sha256'], checkpoint)
            self.assertEqual(server.calls, boundary)
            server.refresh_failure = False
            prune.apply(server, server.provider, plan, plan['sha256'], checkpoint)

    def test_stale_raw_evidence_after_detach_and_forged_binding_fail(self):
        for rebind in (False, True):
            server, state, topology, raw, plan = self.server()
            boundary = next(i for i, op in enumerate(plan['operations']) if op['method'] == 'DELETE')
            for op in plan['operations'][:boundary]:
                state.update(prune.advance(state, op))
            stale = copy.deepcopy(state)
            stale['dependency_evidence'] = copy.deepcopy(raw['dependency_evidence'])
            if rebind:
                ev = stale['dependency_evidence']
                ev['facts_sha256'] = prune.digest(prune.safety_projection(prune.normalized(stale)))
                ev['sha256'] = prune.digest({k: v for k, v in ev.items() if k != 'sha256'})
            with self.subTest(rebind=rebind), self.assertRaises(LabError):
                prune.apply(server, lambda: copy.deepcopy(stale), plan, plan['sha256'])
            self.assertEqual(server.calls, 0)

    def test_unowned_external_module_history_or_address_tag_blocks_staging(self):
        for defect in ('unowned', 'external', 'module', 'history', 'address-tag'):
            server, state, topology, raw, plan = self.server()
            if defect == 'unowned':
                raw[prune.TABLES[2]][0]['description'] = 'manual'
            ev = raw['dependency_evidence']
            if defect == 'external':
                ev['blockers'].append({'reason': 'external address reference'})
            if defect in ('module', 'history'):
                ev['effects'].append({'model': 'dcim.module' if defect == 'module' else 'core.objectchange',
                                      'id': 99, 'owned': True})
            if defect == 'address-tag':
                ev['effects'].append({'model': 'extras.taggeditem', 'id': 99, 'owned': True,
                                      'parent_model': 'ipam.ipaddress', 'parent_id': 3, 'tag': 'fhs-netbox-lab'})
            ev['facts_sha256'] = prune.digest(prune.safety_projection(prune.normalized(raw)))
            ev['sha256'] = prune.digest({k: v for k, v in ev.items() if k != 'sha256'})
            with self.subTest(defect=defect), self.assertRaises(LabError):
                prune.plan(raw, topology)

    def test_post_detach_new_protected_reference_stops_before_delete(self):
        server, state, topology, raw, plan = self.server()
        boundary = next(i for i, op in enumerate(plan['operations']) if op['method'] == 'DELETE')
        def provider():
            fresh = server.provider()
            if server.calls >= boundary:
                ev = fresh['dependency_evidence']
                ev['blockers'].append({'reason': 'protected or restricted relation'})
                ev['sha256'] = prune.digest({k: v for k, v in ev.items() if k != 'sha256'})
            return fresh
        with self.assertRaisesRegex(LabError, 'Fresh scoped collector'):
            prune.apply(server, provider, plan, plan['sha256'], batch_size=100)
        self.assertEqual(server.calls, boundary)
        self.assertEqual(len(state[prune.TABLES[0]]), 183)
