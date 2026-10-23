#!/usr/bin/env python3
"""Real REST lifecycle tests; keep synthetic fixtures for browser inspection."""
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parent
credentials = json.loads((root / 'credentials.json').read_text())
base = credentials['url'].rstrip('/')
report = {'base_url': base, 'synthetic_only': True, 'checks': [], 'snapshots': {}}
report.update(json.loads((root / 'metadata.json').read_text()))
report['dac_scope'] = 'Manual standalone asset status/location transitions; no native Cable assignment/removal integration tested.'


def api(path, data=None, method='GET'):
    req = Request(base + '/api/' + path, method=method,
                  data=None if data is None else json.dumps(data).encode(),
                  headers={'Authorization': 'Token ' + credentials['token'],
                           'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=60) as response:
            body = response.read()
            return json.loads(body) if body else None
    except HTTPError as error:
        raise RuntimeError(f'{method} {path}: {error.code}: {error.read().decode()}') from None


def check(condition, text):
    if not condition:
        raise AssertionError(text)
    report['checks'].append(text)
    print('PASS:', text)


def ensure(path, lookup, values):
    found = api(path + '?' + urlencode(lookup))['results']
    if found:
        if len(found) != 1:
            raise AssertionError(f'Ambiguous synthetic fixture {path}')
        return found[0]
    return api(path, values, 'POST')


def update(path, obj, **values):
    return api(f'{path}{obj["id"]}/', values, 'PATCH')


assets = 'plugins/inventory/assets/'
status = api('status/')
report['status'] = status
check(status['netbox-version'].startswith('4.7.0'), 'Pinned NetBox 4.7.0 serves REST API')
check(status['plugins']['netbox_inventory'] == '2.7.1', 'NetBox Inventory 2.7.1 loaded')
choices = api(assets, method='OPTIONS')['actions']['POST']['status']['choices']
report['asset_status_choices'] = choices
check('faulty' in [item['value'] for item in choices], 'Custom Faulty / quarantine choice available')
site = ensure('dcim/sites/', {'slug': 'inventory-trial'}, {
    'name': 'Synthetic inventory lab', 'slug': 'inventory-trial', 'status': 'active'})
shelf = ensure('dcim/locations/', {'slug': 'spares-shelf-a'}, {
    'name': 'Spares shelf A', 'slug': 'spares-shelf-a', 'site': site['id'], 'status': 'active'})
quarantine = ensure('dcim/locations/', {'slug': 'quarantine-shelf-q1'}, {
    'name': 'Quarantine shelf Q1', 'slug': 'quarantine-shelf-q1', 'site': site['id'], 'status': 'active'})
manufacturer = ensure('dcim/manufacturers/', {'slug': 'synthetic-lab'}, {
    'name': 'Synthetic lab hardware', 'slug': 'synthetic-lab'})
dac_type = ensure('plugins/inventory/inventory-item-types/', {'slug': 'dac-100g-3m'}, {
    'manufacturer': manufacturer['id'], 'model': 'DAC 100G 3m', 'slug': 'dac-100g-3m',
    'description': 'Synthetic standalone cable asset; no native Cable association'})
fpga_type = ensure('dcim/module-types/', {'model': 'FPGA accelerator trial'}, {
    'manufacturer': manufacturer['id'], 'model': 'FPGA accelerator trial', 'part_number': 'SYN-FPGA-01'})
host_type = ensure('dcim/device-types/', {'slug': 'trial-fhs'}, {
    'manufacturer': manufacturer['id'], 'model': 'Trial FHS chassis', 'slug': 'trial-fhs'})
role = ensure('dcim/device-roles/', {'slug': 'synthetic-trial'}, {
    'name': 'Synthetic trial chassis', 'slug': 'synthetic-trial', 'color': '607d8b'})
device = ensure('dcim/devices/', {'name': 'SYNTHETIC-FHS-01'}, {
    'name': 'SYNTHETIC-FHS-01', 'device_type': host_type['id'], 'role': role['id'],
    'site': site['id'], 'status': 'active'})
bay = ensure('dcim/module-bays/', {'device_id': device['id'], 'name': 'FPGA slot 1'}, {
    'device': device['id'], 'name': 'FPGA slot 1', 'position': '1'})

dac = ensure(assets, {'serial': 'SYN-DAC-2026-0001'}, {
    'name': 'Removed DAC — failed test', 'serial': 'SYN-DAC-2026-0001',
    'asset_tag': 'LAB-DAC-001', 'status': 'stored', 'inventoryitem_type': dac_type['id'],
    'storage_location': shelf['id'], 'description': 'Synthetic DAC lifecycle fixture'})
dac = update(assets, dac, status='used', comments='Synthetic trial: DAC in use. Standalone inventory record; native cable linking excluded.')
report['snapshots']['dac_used'] = dac
dac = update(assets, dac, status='faulty', storage_location=quarantine['id'],
             comments='Synthetic trial: removed from service after failed continuity test; stored on Quarantine shelf Q1. Do not reuse until inspected.')
report['snapshots']['dac_removed_faulty'] = dac
ensure(assets, {'serial': 'SYN-DAC-2026-0002'}, {
    'name': 'DAC spare — available', 'serial': 'SYN-DAC-2026-0002',
    'asset_tag': 'LAB-DAC-002', 'status': 'stored', 'inventoryitem_type': dac_type['id'],
    'storage_location': shelf['id'], 'description': 'Synthetic spare; search-filter control'})
for query in [{'q': dac['serial']}, {'serial': dac['serial'], 'status': 'faulty'},
              {'storage_location_id': quarantine['id'], 'status': 'faulty'}]:
    found = api(assets + '?' + urlencode(query))['results']
    check([item['id'] for item in found] == [dac['id']], f'DAC same asset uniquely searchable after removal: {query}')
check(dac['storage_location']['id'] == quarantine['id'] and dac['status'] == 'faulty',
      'Removed DAC retains serial, Faulty status and quarantine shelf')

fpga = ensure(assets, {'serial': 'SYN-FPGA-2026-0001'}, {
    'name': 'FPGA spare — installation lifecycle', 'serial': 'SYN-FPGA-2026-0001',
    'asset_tag': 'LAB-FPGA-001', 'status': 'stored', 'module_type': fpga_type['id'],
    'storage_location': shelf['id'], 'description': 'Synthetic FPGA lifecycle fixture'})
check(fpga['module'] is None, 'FPGA starts as spare without installed module')
original_id = fpga['id']
original_serial = fpga['serial']
report['snapshots']['fpga_spare'] = fpga
module = api('dcim/modules/', {'device': device['id'], 'module_bay': bay['id'],
             'module_type': fpga_type['id'], 'status': 'active'}, 'POST')
fpga = update(assets, fpga, module=module['id'], comments='Synthetic trial: spare FPGA installed in SYNTHETIC-FHS-01, FPGA slot 1.')
report['snapshots']['fpga_installed'] = fpga
check(fpga['status'] == 'used' and fpga['module']['id'] == module['id'],
      'Assigning spare FPGA to installed module automatically sets Used')
installed_module = api(f'dcim/modules/{module["id"]}/')
check(installed_module['serial'] == original_serial and installed_module['asset_tag'] == 'LAB-FPGA-001',
      'Asset serial and asset tag synchronize to installed module')
api(f'dcim/modules/{module["id"]}/', method='DELETE')
fpga = api(f'{assets}{original_id}/')
report['snapshots']['fpga_removed'] = fpga
check(fpga['id'] == original_id and fpga['serial'] == original_serial and fpga['module'] is None,
      'Deleting installed module preserves original FPGA asset ID and serial')
check(fpga['status'] == 'stored' and fpga['storage_location']['id'] == shelf['id'],
      'Removing installed module automatically returns FPGA to Stored and spares shelf')
check(api(assets + '?' + urlencode({'q': original_serial}))['results'][0]['id'] == original_id,
      'Removed FPGA searchable by original serial')
fpga = update(assets, fpga,
              comments='Synthetic trial: FPGA removed from SYNTHETIC-FHS-01, FPGA slot 1; installed module deleted. Original asset and serial retained, returned to Spares shelf A. See change log for installation/removal.')

for name, obj in [('dac', dac), ('fpga', fpga)]:
    history = api('core/object-changes/?' + urlencode({
        'changed_object_type': 'netbox_inventory.asset', 'changed_object_id': obj['id'], 'limit': 100}))
    rows = history['results']
    check(len(rows) >= 3, f'{name.upper()} has real retained NetBox change-log rows')
    statuses = {(r.get('postchange_data') or {}).get('status') for r in rows}
    expected = {'stored', 'used', 'faulty'} if name == 'dac' else {'stored', 'used'}
    check(expected <= statuses, f'{name.upper()} change log contains lifecycle statuses {sorted(expected)}')
    report[name + '_history'] = rows

report['fixture_urls'] = {
    'asset_list': '/plugins/inventory/assets/',
    'dac': f'/plugins/inventory/assets/{dac["id"]}/',
    'dac_history': f'/plugins/inventory/assets/{dac["id"]}/changelog/',
    'fpga': f'/plugins/inventory/assets/{fpga["id"]}/',
    'fpga_history': f'/plugins/inventory/assets/{fpga["id"]}/changelog/',
}
(root / 'acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'{len(report["checks"])} checks passed; sanitized acceptance.json saved.')
