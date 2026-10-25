#!/usr/bin/env python3
"""Exercise real topology module against disposable NetBox objects on delivered chart."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid
from urllib.request import Request, urlopen
import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    credentials = json.loads(Path(args.credentials).read_text())
    base = credentials['url'].rstrip('/'); token = credentials['token']
    prefix = 'SYN-TOPO-' + uuid.uuid4().hex[:8]; checks = []
    def api(path, data=None):
        request = Request(base + '/api/' + path, data=json.dumps(data).encode() if data is not None else None,
            headers={'Authorization': ('Bearer ' if token.startswith('nbt_') else 'Token ') + token, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=45) as response:
            return json.load(response)
    def check(value, message):
        if not value: raise AssertionError(message)
        checks.append(message); print('PASS:', message, flush=True)
    site = api('dcim/sites/', dict(name=prefix, slug=prefix.lower()))
    maker = api('dcim/manufacturers/', dict(name=prefix, slug=prefix.lower()))
    dtype = api('dcim/device-types/', dict(model=prefix, slug=prefix.lower(), manufacturer=maker['id']))
    role = api('dcim/device-roles/', dict(name=prefix, slug=prefix.lower(), color='123456'))
    devices = []
    for suffix in ('switch', 'host'):
        devices.append(api('dcim/devices/', dict(name=prefix + '-' + suffix, device_type=dtype['id'], site=site['id'], role=role['id'])))
    ports = [api('dcim/interfaces/', dict(device=devices[0]['id'], name='Ethernet1/1', type='other')),
             api('dcim/interfaces/', dict(device=devices[1]['id'], name='C0-QSFP0', type='other'))]
    observations = [dict(device=d['name'], serials=[dict(port=p['name'], serial=prefix, kind=k)])
                    for d, p, k in zip(devices, ports, ('nexus', 'fpga'))]
    source = Path(__file__).resolve().parents[3] / 'playbooks/netbox'
    with tempfile.TemporaryDirectory(prefix='fhs-topology-') as temporary:
        folder = Path(temporary)
        binary = folder / 'bin'; binary.mkdir()
        for name, output in {'lldpcli': '{}', 'ethtool': 'Vendor SN : ' + prefix + '\nIdentifier : Passive Copper DAC', 'bw_qsfp_info': 'QSFP0:\n vendor_serial_number : ' + prefix}.items():
            executable = binary / name
            executable.write_text('#!/usr/bin/env python3\nprint(' + repr(output) + ')\n')
            executable.chmod(0o700)
        params = dict(netbox_url=base, netbox_token="{{ lookup('env', 'FHS_TOPOLOGY_TOKEN') }}", observations="{{ [switch_topology, fhs_topology | combine({'serials': fhs_topology.serials | selectattr('kind', 'equalto', 'fpga') | list})] }}")
        play = [dict(hosts='localhost', gather_facts=False, connection='local', vars=dict(
            switch_topology=observations[0], facts=dict(hostname=devices[1]['name']), bootstrap_lldp_argv=[str(binary / 'lldpcli')],
            bootstrap_nic_ethtool_argv=[str(binary / 'ethtool')], nic_ports=[dict(interface='eth0')],
            discovered_bittware=dict(cards=[dict(card_index=0)]), bootstrap_bittware_sdk_root=str(folder),
            bootstrap_bittware_venv=str(folder), hardware_command_path='/usr/bin:/bin',
            bootstrap_bittware_qsfp_argv=[str(binary / 'bw_qsfp_info')]), tasks=[
            dict(name='Collect actual Linux topology tasks using synthetic read-only commands', **{'ansible.builtin.include_tasks': str(source / 'tasks/topology_linux.yml')}),
            dict(name='Verify discovered FPGA serial and NIC EEPROM', **{'ansible.builtin.assert': dict(that=[
                'fhs_topology.serials | length == 2', 'fhs_topology.serials[1].port == "C0-QSFP0"'])}),
            dict(name='Preview exact DAC cable', fhs_topology_sync=dict(params, preview=True), register='preview'),
            dict(name='Apply exact DAC cable', fhs_topology_sync=params, register='first'),
            dict(name='Repeat observation', fhs_topology_sync=params, register='repeat'),
            dict(name='Assert preview, creation and idempotency', **{'ansible.builtin.assert': dict(that=[
                'preview.changed', 'first.changed', 'not repeat.changed', 'repeat.omissions | length == 0'])})])]
        (folder / 'play.yml').write_text(yaml.safe_dump(play, sort_keys=False))
        env = dict(os.environ, FHS_TOPOLOGY_TOKEN=token, ANSIBLE_LIBRARY=str(source / 'library'),
                   ANSIBLE_MODULE_UTILS=str(source / 'module_utils'), ANSIBLE_FILTER_PLUGINS=str(source / 'filter_plugins'))
        result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(folder / 'play.yml')], env=env, text=True, capture_output=True)
        print(result.stdout)
        if result.returncode: raise RuntimeError(result.stderr + result.stdout)
        check(True, 'Native topology module preview, apply and repeat passed')
    actual = [api(f'dcim/interfaces/{p["id"]}/') for p in ports]
    check(actual[0]['cable']['id'] == actual[1]['cable']['id'], 'Both interfaces terminate the same persisted cable')
    Path(args.report).write_text(json.dumps(dict(prefix=prefix, checks=checks, retained_synthetic_devices=[d['name'] for d in devices]), indent=2) + '\n')


if __name__ == '__main__': main()
