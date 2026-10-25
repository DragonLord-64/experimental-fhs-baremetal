#!/usr/bin/env python3
"""Actual optional FRU tasks + importer writes against isolated chart NetBox.

Supply the same private URL/token JSON as acceptance.py. Synthetic fixtures are
retained for user review. Hardware discovery uses only this script's fake tools.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from urllib.request import Request, urlopen
from urllib.parse import urlencode

import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    credentials = json.loads(Path(args.credentials).read_text())
    base = credentials['url'].rstrip('/'); token = credentials['token']
    root = Path(__file__).resolve().parents[3]
    source = root / 'playbooks/netbox'
    prefix = 'SYN-FRU-' + uuid.uuid4().hex[:8]
    checks = []

    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label); print('PASS:', label, flush=True)

    def api(path):
        request = Request(base + '/api/' + path, headers={
            'Authorization': ('Bearer ' if token.startswith('nbt_') else 'Token ') + token})
        with urlopen(request, timeout=45) as response:
            return json.load(response)

    def rows(path, **filters):
        return api(path + '?' + urlencode(dict(filters, limit=1000)))['results']

    status = api('status/')
    check(status['netbox-version'].startswith('4.7.0') and status['plugins'].get('netbox_inventory') == '2.7.1',
          'Delivered chart NetBox/Inventory versions active')
    full = (Path(__file__).parent / 'fixtures/fru.txt').read_text().replace('SYN-', prefix + '-')
    definition = yaml.safe_load((source / 'netbox_import.yml').read_text())[1]
    with tempfile.TemporaryDirectory(prefix='fhs-fru-acceptance-') as temporary:
        folder = Path(temporary); binary = folder / 'bin'; binary.mkdir()
        (binary / 'cat').write_text('#!' + sys.executable + '\nprint("To be filled by OEM")\n')
        (binary / 'cat').chmod(0o700)
        variables = dict(yaml.safe_load((source / 'defaults.yml').read_text()), **definition['vars'])
        variables.update(netbox_url=base, netbox_token="{{ lookup('env', 'FHS_FRU_TOKEN') }}",
            netbox_validate_certs=True, hardware_simulation=True, hardware_command_path=str(binary),
            netbox_api_retries=1, netbox_api_retry_delay=0, netbox_api_loop_pause=0,
            facts=dict(hostname=prefix, system_vendor='To be filled by OEM', product_name='Default string',
                       distribution='Synthetic', distribution_version='1'),
            ansible_python_interpreter=sys.executable, server_info={},
            resource_fields=dict(cpus=16, ram=65536), resource_field_types={}, netbox_resource_fields={},
            hardware_fields=dict(bios_version='SYN-BIOS', bmc_firmware='SYN-BMC'), discovered_components=[],
            discovered_interfaces=[], ip_ownership=[], mac_ownership=[], selected_primary_ipv4={})
        env = dict(os.environ, ANSIBLE_LIBRARY=str(source / 'library'),
            ANSIBLE_MODULE_UTILS=str(source / 'module_utils'), ANSIBLE_FILTER_PLUGINS=str(source / 'filter_plugins'),
            ANSIBLE_HOME=str(folder / 'home'), ANSIBLE_LOCAL_TEMP=str(folder / 'tmp'),
            ANSIBLE_NOCOLOR='1', ANSIBLE_STDOUT_CALLBACK='default', FHS_FRU_TOKEN=token)

        def run(output=None, rc=0):
            tool = binary / 'ipmitool'
            if output is None:
                if tool.exists(): tool.unlink()
            else:
                tool.write_text('#!' + sys.executable + '\nimport sys\nprint(' + repr(output) + ')\nsys.exit(' + str(rc) + ')\n')
                tool.chmod(0o700)
            (folder / 'vars.json').write_text(json.dumps(variables))
            tasks = [dict(name='Seed synthetic host facts', tags=['always'], **{'ansible.builtin.set_fact': {
                'ansible_facts': {'hostname': '{{ facts.hostname }}'}, 'discovered_interfaces': []}})]
            for filename in ('identity.yml', 'compare.yml', 'apply.yml'):
                task = {'ansible.builtin.import_tasks': str(source / 'tasks' / filename)}
                if filename == 'apply.yml':
                    task['when'] = yaml.safe_load((source / 'tasks/import_linux.yml').read_text())[-1]['when']
                tasks.append(task)
            play = dict(hosts='localhost', connection='local', gather_facts=False,
                        vars_files=[str(folder / 'vars.json')], module_defaults=definition['module_defaults'], tasks=tasks)
            (folder / 'play.yml').write_text(yaml.safe_dump([play], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(folder / 'play.yml'), '--tags', 'apply'],
                env=env, cwd=folder, text=True, capture_output=True, timeout=240)
            Path(args.report + '.last-log').write_text((result.stdout + result.stderr).replace(token, '<redacted>'))
            if result.returncode:
                raise AssertionError((result.stdout + result.stderr).replace(token, '<redacted>'))
            return result.stdout

        run(full)
        device = rows('dcim/devices/', name=prefix)[0]; did = device['id']; fields = device['custom_fields']
        check(device['serial'] == prefix + '-CHASSIS-001' and fields['product_serial'] == prefix + '-PRODUCT-001'
              and fields['motherboard_serial'] == prefix + '-BOARD-001', 'Actual apply preserves all three separate serial identities')
        check(device['device_type']['model'] == prefix + '-SERVER-PART', 'Date-shaped FRU product name falls back to actual part')
        check(fields['bios_version'] == 'SYN-BIOS' and fields['bmc_firmware'] == 'SYN-BMC'
              and fields['product_version'] == '0.2.0.0.0', 'FRU product version remains separate from BIOS/BMC firmware')
        check(fields['hardware_identity_sources']['serial'] == 'ipmitool fru ID 0: Chassis Serial'
              and fields['fru_inventory']['0']['fields']['Chassis Serial'] == device['serial']
              and fields['fru_inventory']['3']['fields']['Product Serial'] == prefix + '-PSU-001', 'Provenance and separate FRU records persisted through native modules')
        board = rows('dcim/inventory-items/', device_id=did, name='Motherboard')[0]
        check(board['serial'] == prefix + '-BOARD-001' and board['manufacturer']['name'] == 'ASRockRack',
              'Motherboard item uses observed board serial and manufacturer')
        assets = {a['serial']: a['id'] for a in rows('plugins/inventory/assets/') if a['serial'].startswith(prefix)}
        check(set(assets) == {prefix + '-CHASSIS-001', prefix + '-BOARD-001'}, 'Only chassis and motherboard have physical assets')
        output = run(full)
        check('changed=0' in output, 'Repeated full native task import is idempotent')
        # Correct manufacturer, then model, while retaining the same physical asset.
        corrected = full.replace('BittWare', 'SYN-Observed-Vendor')
        run(corrected)
        updated = rows('dcim/devices/', name=prefix)[0]
        chassis_asset = rows('plugins/inventory/assets/', device_id=did)[0]
        check(updated['id'] == did and updated['device_type']['model'] == prefix + '-SERVER-PART'
              and updated['device_type']['manufacturer']['name'] == 'SYN-Observed-Vendor',
              'FRU manufacturer/model correct existing device')
        check(chassis_asset['id'] == assets[prefix + '-CHASSIS-001']
              and chassis_asset['device_type']['id'] == updated['device_type']['id'],
              'Real Inventory plugin retains asset ID and corrects its type with device')
        check('changed=0' in run(corrected), 'Corrected native import is idempotent')
        corrected = corrected.replace(prefix + '-SERVER-PART', prefix + '-CORRECTED-PART')
        run(corrected)
        check(rows('dcim/devices/', name=prefix)[0]['device_type']['model'] == prefix + '-CORRECTED-PART'
              and rows('plugins/inventory/assets/', device_id=did)[0]['id'] == chassis_asset['id'],
              'Observed model correction also retains the same chassis asset')
        # Return to the original observations before partial-read preservation checks.
        run(full)
        variables['hardware_fields'] = {}; variables['resource_fields'] = {}
        run('FRU Device Description : Builtin FRU Device (ID 0)\n Product Version : 2\n')
        partial = rows('dcim/devices/', name=prefix)[0]['custom_fields']
        check(partial['product_version'] == '2' and partial['product_serial'] == fields['product_serial']
              and partial['motherboard_serial'] == fields['motherboard_serial'] and partial['cpus'] == 16,
              'Partial FRU updates observed field and retains known identity/resources')
        check(partial['bios_version'] == 'SYN-BIOS' and partial['bmc_firmware'] == 'SYN-BMC'
              and partial['fru_inventory']['0']['fields']['Chassis Serial'] == device['serial'],
              'Partial metadata merge preserves firmware and prior FRU fields')
        for output, rc in [(full, 1), (None, 0)]:
            run(output, rc)
            preserved = rows('dcim/devices/', name=prefix)[0]
            check(preserved['serial'] == device['serial'] and preserved['custom_fields'] == partial,
                  'Failed or missing IPMI preserves existing values and provenance')
        check(rows('dcim/inventory-items/', device_id=did)[0]['id'] == board['id'] and
              {a['serial']: a['id'] for a in rows('plugins/inventory/assets/') if a['serial'].startswith(prefix)} == assets,
              'Partial/failed/missing FRU preserves installed motherboard and asset IDs')
        variables['facts']['hostname'] = prefix + '-NO-TYPE'
        output = run()
        check(not rows('dcim/devices/', name=variables['facts']['hostname']) and 'No usable FRU serial' in output,
              'No IPMI or usable type reports and skips new device without failing')
        # A serial alone must be sufficient, even with misleading Linux DMI facts.
        variables['facts'].update(system_vendor='IGNORED-DMI', product_name='IGNORED-DMI', product_serial='IGNORED-DMI')
        variables['facts']['hostname'] = prefix + '-SERIAL-ONLY'
        serial_only = 'FRU Device Description : System (ID 0)\n Product Serial : ' + prefix + '-MINIMAL\n'
        run(serial_only)
        minimal = rows('dcim/devices/', name=variables['facts']['hostname'])[0]
        check(minimal['serial'] == prefix + '-MINIMAL' and minimal['device_type']['model'] == 'Unknown'
              and minimal['device_type']['manufacturer']['name'] == 'NA',
              'FRU serial alone creates device with NA manufacturer and Unknown type; DMI ignored')
        check('changed=0' in run(serial_only), 'Serial-only device import is idempotent')
        variables.update(bootstrap_manufacturer='SYN-Override-Vendor', bootstrap_device_type=prefix + '-OVERRIDE',
                         bootstrap_chassis_serial=prefix + '-OVERRIDE-SERIAL')
        variables['facts']['hostname'] = prefix + '-OVERRIDE-HOST'
        run('FRU Device Description : System (ID 0)\n Chassis Serial : ' + prefix + '-IGNORED\n'
            ' Product Manufacturer : FRU vendor\n Product Name : FRU model\n')
        explicit = rows('dcim/devices/', name=variables['facts']['hostname'])[0]
        check(explicit['serial'] == prefix + '-OVERRIDE-SERIAL'
              and explicit['device_type']['manufacturer']['name'] == 'SYN-Override-Vendor'
              and explicit['device_type']['model'] == prefix + '-OVERRIDE',
              'Explicit identity overrides take precedence over FRU and DMI')
    report = dict(synthetic_only=True, run=prefix, checks=checks, checks_passed=len(checks),
                  device_id=did, motherboard_id=board['id'], status=status)
    Path(args.report).write_text(json.dumps(report, indent=2) + '\n')
    print(str(len(checks)) + ' checks passed; report ' + args.report)


if __name__ == '__main__':
    main()
