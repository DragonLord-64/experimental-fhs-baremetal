"""Peer URLs must survive Grafana display mappings and table transforms."""
import json
import re
import unittest

from test_refinements import ROOT, load


class PeerContext(unittest.TestCase):
    def test_native_url_is_composed_from_mapping_safe_components(self):
        # Actual Grafana 13 still mapped full hidden identities despite mappings=[].
        # Inspect the real generated panel and persisted candidate, not a URL helper.
        for name, peer in self.peers():
            with self.subTest(candidate=name):
                url = peer['fieldConfig']['defaults']['links'][0]['url']
                unit = '${__data.fields.peer_role:percentencode}Unit${__data.fields.peer_number:percentencode}'
                self.assertIn('var-unit=' + unit + '&', url)
                self.assertIn('var-switch=' + unit + '-switch&', url)
                self.assertIn('var-interface=${__data.fields.portIdV:percentencode}', url)
                self.assertNotRegex(url, r'__data\.fields\.(?:sysName|peer_unit|peer_switch)[:}]')
                expr = peer['targets'][0]['expr']
                self.assertIn('"peer_role","$1","sysName","(VCC|FSP)Unit([0-9]+)-switch"', expr)
                self.assertIn('"peer_number","$2","sysName","(VCC|FSP)Unit([0-9]+)-switch"', expr)

    def test_mapping_safe_components_remain_hidden_frame_fields(self):
        for name, peer in self.peers():
            for field in ('peer_role', 'peer_number'):
                with self.subTest(candidate=name, field=field):
                    overrides = {o['matcher']['options']: {
                        p['id']: p['value'] for p in o['properties']}
                        for o in peer['fieldConfig']['overrides']
                        if o['matcher']['id'] == 'byName'}
                    self.assertTrue(overrides.get(field, {}).get('custom.hidden'),
                                    'Retain identity components using table-only hiding')
                    self.assertEqual([], overrides[field].get('mappings'))
                    for transform in peer.get('transformations', []):
                        if transform['id'] == 'organize':
                            options = transform['options']
                            self.assertFalse(options.get('excludeByName', {}).get(field, False))
                            if options.get('includeByName'):
                                self.assertTrue(options['includeByName'].get(field))

    def peers(self):
        candidates = {
            'generator': load('generate').build()['interface'],
            'checked-in': json.loads((ROOT / 'generated/interface.json').read_text()),
        }
        for name, dashboard in candidates.items():
            yield name, next(p for p in dashboard['panels']
                             if p['title'] == 'Last-known peer')

    def linked_fields(self, peer):
        url = peer['fieldConfig']['defaults']['links'][0]['url']
        fields = re.findall(r'\$\{__data\.fields\.([^}:]+):percentencode\}', url)
        self.assertEqual(['peer_role', 'peer_number', 'peer_role', 'peer_number', 'portIdV'],
                         fields, 'Unit and switch must use the retained native components')
        return fields

    def test_url_identity_fields_survive_organize_transform(self):
        for name, peer in self.peers():
            for field in self.linked_fields(peer):
                with self.subTest(candidate=name, field=field):
                    for transform in peer.get('transformations', []):
                        if transform['id'] != 'organize':
                            continue
                        options = transform['options']
                        self.assertFalse(options.get('excludeByName', {}).get(field, False),
                                         'Table hiding must retain the native field in the frame')
                        if options.get('includeByName'):
                            self.assertTrue(options['includeByName'].get(field))

    def test_url_identity_fields_disable_inherited_display_mappings(self):
        for name, peer in self.peers():
            for field in self.linked_fields(peer):
                with self.subTest(candidate=name, field=field):
                    mappings = peer['fieldConfig']['defaults'].get('mappings', [])
                    for override in peer['fieldConfig'].get('overrides', []):
                        matcher = override['matcher']
                        if matcher['id'] == 'byName' and matcher['options'] == field:
                            for prop in override['properties']:
                                if prop['id'] == 'mappings':
                                    mappings = prop['value']
                    self.assertEqual([], mappings,
                                     'Grafana data-link macros expand mapped display values')

    def test_native_components_are_hidden_only_in_table_and_visible_peer_stays_mapped(self):
        for name, peer in self.peers():
            with self.subTest(candidate=name):
                expr = peer['targets'][0]['expr']
                self.assertIn('"peer_role","$1","sysName","(VCC|FSP)Unit([0-9]+)-switch"', expr)
                self.assertIn('"peer_number","$2","sysName","(VCC|FSP)Unit([0-9]+)-switch"', expr)
                self.assertIn('interface="$interface"', expr)
                self.assertIn('source="$switch"', expr)
                overrides = {o['matcher']['options']: {
                    p['id']: p['value'] for p in o['properties']}
                    for o in peer['fieldConfig']['overrides']
                    if o['matcher']['id'] == 'byName'}
                for field in ('peer_role', 'peer_number'):
                    self.assertTrue(overrides[field]['custom.hidden'])
                self.assertFalse(overrides.get('sysName', {}).get('custom.hidden', False))
                self.assertFalse(overrides['portIdV'].get('custom.hidden', False))
                mappings = peer['fieldConfig']['defaults']['mappings']
                self.assertTrue(any(m['type'] == 'regex' and
                                    m['options']['result']['text'] == 'fspu$1$2'
                                    for m in mappings))
                order = peer['transformations'][0]['options']['indexByName']
                self.assertEqual([0, 1, 2, 3],
                                 [order[f] for f in ('sysName', 'portIdV', 'interface', 'mgmtIp')])
