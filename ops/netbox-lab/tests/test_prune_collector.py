"""Collector plan boundary regressions; no Django or live connections."""
import unittest

from test_prune import fixture
import prune
from inventory import LabError


class CollectorBoundaryTests(unittest.TestCase):
    def test_refresh_requires_complete_frozen_scope_even_when_finished(self):
        import collector
        scope = {table: [] for table in prune.TABLES}
        collector.validate_scope([], scope)
        for selected, frozen in (([], None), ([], {}), ([1], scope),
                                 ([True], None), ([1, 1], None)):
            with self.subTest(selected=selected, frozen=frozen), self.assertRaises(RuntimeError):
                collector.validate_scope(selected, frozen)
        scope[prune.TABLES[0]] = [1]
        collector.validate_scope([1], scope)
        scope[prune.TABLES[2]] = [2, 2]
        with self.assertRaisesRegex(RuntimeError, 'Invalid frozen scope'):
            collector.validate_scope([1], scope)

    def test_physical_module_interface_is_preserved_without_module_cascade(self):
        state, topology = fixture()
        state[prune.TABLES[1]][0]['module'] = {'id': 765}
        with self.assertRaisesRegex(LabError, 'Physical module interface'):
            prune.plan(state, topology)

    def test_physical_inventory_and_history_cascades_are_rejected(self):
        for model in ('dcim.module', 'dcim.inventoryitem', 'core.objectchange'):
            state, topology = fixture()
            evidence = state['dependency_evidence']
            evidence['effects'].append({'model': model, 'id': 99999, 'owned': True})
            evidence['sha256'] = prune.digest({k: v for k, v in evidence.items() if k != 'sha256'})
            with self.subTest(model=model), self.assertRaises(LabError):
                prune.plan(state, topology)

    def test_unowned_cascade_is_rejected_even_with_valid_hash(self):
        state, topology = fixture()
        evidence = state['dependency_evidence']
        evidence['effects'][0]['owned'] = False
        evidence['sha256'] = prune.digest({k: v for k, v in evidence.items() if k != 'sha256'})
        with self.assertRaises(LabError):
            prune.plan(state, topology)

    def test_unowned_collector_field_update_is_rejected(self):
        state, topology = fixture()
        evidence = state['dependency_evidence']
        evidence['updates'].append({'model': 'dcim.device', 'id': 99999,
                                    'field': 'primary_ip4', 'null': True})
        evidence['sha256'] = prune.digest({k: v for k, v in evidence.items() if k != 'sha256'})
        with self.assertRaises(LabError):
            prune.plan(state, topology)

    def test_out_of_range_batch_rejected_before_provider_or_write(self):
        state, topology = fixture()
        plan = prune.plan(state, topology)
        def forbidden(*args):
            self.fail('Invalid batch must not read or write')
        for size in (0, 101):
            with self.subTest(size=size), self.assertRaises(LabError):
                prune.apply(None, forbidden, plan, plan['sha256'], batch_size=size)

    def test_only_owned_synthetic_tag_assignments_may_cascade(self):
        for parent, tag, allowed in ((1, 'lab-logical', True), (99999, 'lab-logical', False),
                                     (1, 'manual-policy', False)):
            state, topology = fixture()
            evidence = state['dependency_evidence']
            evidence['effects'].append({'model': 'extras.taggeditem', 'id': 88888, 'owned': True,
                                        'parent_model': 'dcim.device', 'parent_id': parent, 'tag': tag})
            evidence['sha256'] = prune.digest({k: v for k, v in evidence.items() if k != 'sha256'})
            with self.subTest(parent=parent, tag=tag):
                if allowed:
                    self.assertEqual(prune.plan(state, topology)['obsolete_logical'], 160)
                else:
                    with self.assertRaises(LabError):
                        prune.plan(state, topology)

    def test_collector_row_guard_checks_iterators_and_queryset_boundary(self):
        import collector
        from unittest.mock import patch
        with patch.object(collector, 'MAX_ROWS', 2):
            self.assertEqual(collector.bounded(iter([1, 2])), [1, 2])
            with self.assertRaisesRegex(RuntimeError, 'row bound'):
                collector.bounded(iter([1, 2, 3, 4]))
            class Query:
                model = object()
                def __getitem__(self, key):
                    self.limit = key.stop
                    return [1, 2, 3]
            query = Query()
            with self.assertRaisesRegex(RuntimeError, 'row bound'):
                collector.bounded(query)
            self.assertEqual(query.limit, 3)
