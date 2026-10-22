"""Actual native capture path with query-counting ORM doubles; no live ORM."""
import json
import sys
import types
import unittest
from unittest.mock import patch

from test_inventory import lab  # Establish the same offline module path as existing tests.
import collector


def field(name, relation=False, choices=()):
    return types.SimpleNamespace(name=name, attname=name + '_id' if relation else name,
                                 is_relation=relation, choices=choices, flatchoices=choices)


class Query:
    def __init__(self, count, fields=None):
        self.count = count
        self.calls = []
        self.model = types.SimpleNamespace(_meta=types.SimpleNamespace(
            concrete_fields=fields or [field('id'), field('serial'), field('status', choices=[('active', 'Active')]),
                field('site', True), field('module', True), field('vrf', True),
                field('custom_field_data'), field('future_safety_field'),
                field('address'), field('mac_address'), field('assigned_object_type', True),
                field('assigned_object_id')],
            related_objects=[types.SimpleNamespace(one_to_one=True, get_accessor_name=lambda: 'parent_bay',
                related_model=types.SimpleNamespace(_meta=types.SimpleNamespace(label_lower='dcim.devicebay')),
                field=types.SimpleNamespace(name='installed_device'))],
            many_to_many=[field('tagged_vlans')]))

    def values(self, *names):
        self.calls.append(names)
        rows = []
        for pk in range(1, self.count + 1):
            values = {'id': pk, 'pk': pk, 'serial': 'physical-' + str(pk), 'status': 'active',
                      'site_id': 7, 'site__slug': 'owned-site', 'module_id': 8,
                      'vrf_id': 9, 'custom_field_data': {'manual': True},
                      'future_safety_field': {'unknown': 'preserved'},
                      'address': '192.0.2.1/24', 'mac_address': '02:00:00:00:00:01',
                      'assigned_object_type_id': 11, 'assigned_object_id': 12,
                      'assigned_object_type__app_label': 'dcim',
                      'assigned_object_type__model': 'interface', 'parent_bay__pk': 13,
                      'tags__pk': 14, 'tags__slug': 'owner', 'tags__name': 'Owner',
                      'tagged_vlans__pk': 15}
            rows.append({name: values[name] for name in names})
        class Values(list):
            def order_by(self, *args):
                return self
        return Values(rows)


class NativeCaptureTests(unittest.TestCase):
    def capture(self, query):
        modules = {'django.core.serializers.json': types.SimpleNamespace(DjangoJSONEncoder=json.JSONEncoder)}
        with patch.dict(sys.modules, modules):
            return collector.native_records(query)

    def test_query_count_constant_for_183_devices_and_parent_bay(self):
        for count in (1, 183, 1000):
            query = Query(count)
            rows = self.capture(query)
            self.assertEqual(len(query.calls), 3)
            self.assertEqual(len(rows), count)
            self.assertEqual(rows[-1]['parent_bay'], {'id': 13})
            self.assertEqual(rows[-1]['_prune_reverse_one_to_one'], {
                'parent_bay': {'model': 'dcim.devicebay', 'field': 'installed_device'}})
            self.assertEqual(rows[-1]['serial'], 'physical-' + str(count))

    def test_all_stored_safety_facts_and_unknown_fields_survive(self):
        row = self.capture(Query(1))[0]
        self.assertEqual(row['status'], {'value': 'active', 'label': 'Active'})
        self.assertEqual(row['site'], {'id': 7, 'slug': 'owned-site'})
        self.assertEqual(row['custom_fields'], {'manual': True})
        self.assertEqual(row['future_safety_field'], {'unknown': 'preserved'})
        for name, pk in [('module', 8), ('vrf', 9), ('tagged_vlans', 15)]:
            self.assertIn({'id': pk}, row[name] if isinstance(row[name], list) else [row[name]])
        self.assertEqual(row['assigned_object_type'], 'dcim.interface')
        self.assertEqual(row['assigned_object_id'], 12)
        self.assertEqual(row['address'], '192.0.2.1/24')
        self.assertEqual(row['mac_address'], '02:00:00:00:00:01')
        self.assertEqual(row['tags'][0]['slug'], 'owner')

    def test_bound_rejects_base_and_relation_fanout(self):
        with patch.object(collector, 'MAX_ROWS', 2):
            with self.assertRaisesRegex(RuntimeError, 'row bound'):
                self.capture(Query(3))
            query = Query(1)
            original = query.values
            def fanout(*names):
                rows = original(*names)
                if 'tags__pk' in names:
                    rows *= 3
                return rows
            query.values = fanout
            with self.assertRaisesRegex(RuntimeError, 'row bound'):
                self.capture(query)

    def test_unknown_native_value_fails_instead_of_disappearing(self):
        query = Query(1)
        original = query.values
        def unsupported(*names):
            rows = original(*names)
            if 'future_safety_field' in names:
                rows[0]['future_safety_field'] = object()
            return rows
        query.values = unsupported
        netaddr = types.SimpleNamespace(IPAddress=type('IP', (), {}), IPNetwork=type('Network', (), {}), EUI=type('MAC', (), {}), mac_unix_expanded=object())
        with patch.dict(sys.modules, {'netaddr': netaddr}), self.assertRaises(TypeError):
            self.capture(query)

    def test_native_ip_and_mac_values_have_canonical_json_identity(self):
        class IP:
            def __str__(self):
                return '192.0.2.1/24'
        class MAC:
            def format(self, dialect):
                return '02:00:00:00:00:01'
        netaddr = types.SimpleNamespace(IPAddress=IP, IPNetwork=type('Network', (), {}),
                                       EUI=MAC, mac_unix_expanded=object())
        query = Query(1)
        original = query.values
        def native(*names):
            rows = original(*names)
            if 'address' in names:
                rows[0]['address'] = IP()
                rows[0]['mac_address'] = MAC()
            return rows
        query.values = native
        with patch.dict(sys.modules, {'netaddr': netaddr}):
            row = self.capture(query)[0]
        self.assertEqual(row['address'], '192.0.2.1/24')
        self.assertEqual(row['mac_address'], '02:00:00:00:00:01')

    def test_taggeditem_effects_join_relations_before_bounded_evaluation(self):
        class Effects:
            model = types.SimpleNamespace(_meta=types.SimpleNamespace(label_lower='extras.taggeditem'))
            _fields = None
            def select_related(self, *names):
                self.joined = names
                return self
            def __getitem__(self, limit):
                self.limit = limit.stop
                return [1]
        query = Effects()
        self.assertEqual(collector.bounded(query), [1])
        self.assertEqual(query.joined, ('content_type', 'tag'))
        self.assertEqual(query.limit, 12001)
