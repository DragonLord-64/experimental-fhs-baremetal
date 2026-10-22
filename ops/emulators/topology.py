#!/usr/bin/env python3
"""Canonical logical inventory; optional full reference is 24 VCC and 27 FSP units."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def topology(vcc_count=24, fsp_count=27):
    if not 1 <= vcc_count <= 24 or not 3 <= fsp_count <= 27:
        raise ValueError('Supported fixture: 1..24 VCC and 3..27 FSP units')
    units, hosts, switches, mesh = [], [], [], []
    for role, number in [(r,n) for r,count in [('vcc',vcc_count),('fsp',fsp_count)] for n in range(1,count+1)]:
        # Preserve original full-inventory identities even when units are omitted.
        ix = number if role == 'vcc' else 24 + number
        unit = f'{role.upper()}Unit{number}'
        switch = {'name': f'{unit}-switch', 'unit': unit, 'role': role,
                  'management_ip': f'192.0.2.{200+ix}', 'chassis_mac': f'02:00:00:ff:{ix:02x}:00', 'links': []}
        unit_hosts = []
        for h in range(1, 2 if role == 'vcc' else 5):
            host = {'name': f'{role}unit{number}-fhs{h}', 'unit': unit, 'role': role, 'fhs': f'FHS{h}',
                    'management_ip': f'192.0.2.{number if role == "vcc" else 24 + (number-1)*4 + h}', 'chassis_mac': f'02:00:00:{ix:02x}:{h:02x}:00',
                    'telemetry': 'missing' if role == 'fsp' and number == 1 else ('psu1_fault' if role == 'fsp' and number == 2 and h == 1 else 'healthy'),
                    'fpga_cards': [f'lab-{ix}-{h}-fpga0', f'lab-{ix}-{h}-fpga1'], 'interfaces': []}
            unit_hosts.append(host['name'])
            for nic in range(2):
                dev, port = f'enp1s0f{nic}', f'eth1/{20+h}/{nic+1}'
                host['interfaces'].append({'node_device': dev, 'node_mac': f'02:00:00:{ix:02x}:{h:02x}:{nic+1:02x}',
                    'speed_bytes': 12500000000, 'switch': switch['name'], 'switch_port': port})
                switch['links'].append({'local_port': port, 'state': 'up', 'kind': 'host',
                    'neighbor': {k:host[k] for k in ('name','management_ip','chassis_mac')}, 'remote_port': dev})
            hosts.append(host)
        units.append({'name':unit,'role':role,'hosts':unit_hosts,'switch':switch['name']})
        switches.append(switch)
    vccs, fsps = [s for s in switches if s['role']=='vcc'], [s for s in switches if s['role']=='fsp']
    def mesh_port(index):
        return f'eth1/{(index-1)//4+1}/{(index-1)%4+1}'
    for vi,vcc in enumerate(vccs,1):
        for fi,fsp in enumerate(fsps,1):
            lp,rp = mesh_port(fi),mesh_port(vi)
            state = 'down' if vi==1 and fi==3 else 'up'
            mesh.append({'a_switch':vcc['name'],'a_port':lp,'b_switch':fsp['name'],'b_port':rp,'state':state})
            for source, remote, local, peer in [(vcc,fsp,lp,rp),(fsp,vcc,rp,lp)]:
                source['links'].append({'local_port':local,'state':state,'kind':'mesh',
                    'neighbor':{k:remote[k] for k in ('name','management_ip','chassis_mac')},'remote_port':peer})
    return {'synthetic':True,'mode':'shared','scenario':'unit-health-and-mesh',
            'units':units,'hosts':hosts,'switches':switches,'mesh_links':mesh}

def configured():
    counts = json.loads(Path(os.environ.get('EMULATOR_CONFIG', ROOT/'config.json')).read_text())
    if counts.get('mode') != 'shared':
        raise ValueError('Only the measured shared-worker mode is implemented')
    return topology(counts['vcc_units'], counts['fsp_units'])

if __name__ == '__main__':
    print(json.dumps(configured(),indent=2))
