#!/usr/bin/env python3
"""Emit every actual host/component query for supervisor execution; no live access."""
import json
from exact import inventory, canonical_name, inventory_fallback, expected_host
from generate import ROOT, component_health, reading_query


def build():
    catalog = json.loads((ROOT / 'components.json').read_text())
    selections = []
    for host in inventory():
        if host['kind'] != 'server' or not host['deployed']:
            continue
        for component in catalog:
            expr = (reading_query({'name': 'sts_psu' + component['title'][-1] + '_fan'}, component['source'])
                    if component['title'].startswith('PSU ') else component_health(component))
            def selected(query):
                return query.replace('$unit', host['unit']).replace('$fhs', host['fhs'])
            selections.append({'host': canonical_name(host['id']), 'unit': host['unit'],
                               'fhs': host['fhs'], 'component': component['title'],
                               'status_query': selected(inventory_fallback(expr, expected_host())),
                               'reading_queries': [selected(reading_query(r, component['source'])) for r in component['readings']]})
    return {'actual_hosts': 16, 'catalog_components': len(catalog),
            'selection_count': len(selections), 'missing_host_selections': 84,
            'requested_168': '168 covers only eight hosts at 21 components; actual scope is 16 hosts / 336 selections. Observed support must be measured per reading.',
            'selections': selections}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
