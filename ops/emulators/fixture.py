#!/usr/bin/env python3
"""Render static, explicitly labelled node fixtures for the logical inventory."""
import json
from pathlib import Path
import sys
from topology import configured

ROOT = Path(__file__).resolve().parent

def labels(host, **extra):
    data = {'unit':host['unit'], 'role':host['role'], 'fhs':host['fhs'], 'fhs_name':host['name'], **extra}
    return ','.join(k+'='+json.dumps(str(v)) for k,v in sorted(data.items()))

def node_metrics(t):
    lines = []
    def define(name, kind='gauge'):
        lines.extend([f'# HELP {name} Synthetic shared logical-host fixture.',f'# TYPE {name} {kind}'])
    present = [h for h in t['hosts'] if h['telemetry'] != 'missing']
    define('node_uname_info')
    for host in present:
        lines.append('node_uname_info{'+labels(host,nodename=host['name'],sysname='Linux',release='lab',version='synthetic',machine='x86_64',domainname='lab.invalid')+'} 1')
    for name,value in [('node_memory_MemTotal_bytes',68719476736),('node_memory_MemAvailable_bytes',51539607552)]:
        define(name)
        for host in present:
            lines.append(name+'{'+labels(host)+'} '+str(value))
    for name,value in [('up',1),('carrier',1),('mtu_bytes',9216),('speed_bytes',None)]:
        metric = 'node_network_'+name
        define(metric)
        for host in present:
            for link in host['interfaces']:
                lines.append(metric+'{'+labels(host,device=link['node_device'])+'} '+str(link['speed_bytes'] if value is None else value))
    define('node_network_info')
    for host in present:
        for link in host['interfaces']:
            lines.append('node_network_info{'+labels(host,device=link['node_device'],address=link['node_mac'],broadcast='ff:ff:ff:ff:ff:ff',duplex='full',operstate='up',ifalias=link['switch']+':'+link['switch_port'])+'} 1')
    for direction in ('receive','transmit'):
        metric = f'node_network_{direction}_bytes_total'
        define(metric,'counter')
        for host in present:
            for link in host['interfaces']:
                lines.append(metric+'{'+labels(host,device=link['node_device'])+'} 1000000')
    return '\n'.join(lines)+'\n'

if __name__ == '__main__':
    t = configured()
    if '--write' in sys.argv:
        (ROOT/'fixtures/topology.json').write_text(json.dumps(t,separators=(',',':'))+'\n')
        (ROOT/'fixtures/node.prom').write_text(node_metrics(t))
    else:
        print(node_metrics(t),end='')
