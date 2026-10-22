#!/usr/bin/env python3
"""Verify real exporter -> Telegraf -> Prometheus contracts on dragonvm."""
import contextlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
K = ['minikube', '-p', 'fhs-test', 'kubectl', '--', '--context=fhs-test', '--request-timeout=30s']

def retry(fn, seconds=150):
    deadline = time.monotonic() + seconds
    while True:
        try:
            return fn()
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(2)

@contextlib.contextmanager
def forward(namespace, service, port):
    with tempfile.TemporaryFile(mode='w+') as log:
        p = subprocess.Popen(K + ['-n', namespace, 'port-forward', '--address=127.0.0.1', f'svc/{service}', f':{port}'], stdout=log, stderr=log, start_new_session=True)
        try:
            def ready():
                if p.poll() is not None:
                    raise RuntimeError(f'{service} port forward exited')
                log.seek(0)
                match = re.search(r'Forwarding from 127.0.0.1:(\d+)', log.read())
                assert match, f'waiting for {service} port forward'
                return int(match.group(1))
            yield retry(ready, 45)
        finally:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
            p.wait(timeout=10)

def get(port, path):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=10) as response:
        return response.read().decode()

def main():
    from topology import configured
    t = configured()
    present = [h for h in t['hosts'] if h['telemetry'] != 'missing']
    with forward('fhs-emulators', 'fhs-emulator', 9110) as fhs, forward('fhs-emulators', 'fhs-emulator', 9111) as fault, forward('fhs-emulators', 'fhs-emulator', 9100) as node, forward('fhs-platform', 'switch-telegraf', 9273) as telegraf, forward('fhs-platform', 'monitoring-prometheus', 9090) as prom:
        def collected(port):
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/metrics', timeout=10) as response:
                stamp = response.headers.get('X-Exporter-Collected-At')
                assert stamp, 'Native-response cache lacks collection timestamp'
                return stamp
        initial = retry(lambda: collected(fhs))
        def refreshed():
            assert collected(fhs) != initial, 'Native snapshot did not refresh'
        retry(refreshed, 30)
        print('PASS actual native cache collection timestamp advances', flush=True)
        raw = retry(lambda: get(fhs, '/metrics'))
        assert 'nic_temperature_celcius{data_type="temperature",source="NIC"} 50.0' in raw
        assert 'sts_psu1_fan{data_type="flag",source="PSU1"} 0.0' in raw
        assert 'sts_psu1_fan{data_type="flag",source="PSU1"} 1.0' in get(fault, '/metrics')
        node_raw = get(node, '/metrics')
        assert 'node_textfile_scrape_error 0' in node_raw
        assert 'node_cpu_seconds_total' not in node_raw
        for host in t['hosts']:
            marker = 'fhs_name="' + host['name'] + '"'
            assert (marker in node_raw) == (host['telemetry'] != 'missing'), host['name']
        print('PASS real healthy/fault FHS exporters, real node textfile exporter; no node data for FSPUnit1', flush=True)
        def query(expr):
            payload = json.loads(get(prom, '/api/v1/query?query=' + urllib.parse.quote(expr)))
            assert payload['status'] == 'success'
            return payload['data']['result']
        def scalar(expr, value):
            result = query(expr)
            assert len(result)==1 and float(result[0]['value'][1])==value, (expr,result)
        retry(lambda: scalar('count(up{job="fhs-emulator"})', len(t['hosts'])))
        retry(lambda: scalar('count(up{job="fhs-emulator",unit="FSPUnit1"} == 0)', 4))
        retry(lambda: scalar('count(up{job="fhs-emulator"} == 1)', len(present)))
        def absent():
            assert not query('{job="fhs-emulator",unit="FSPUnit1",__name__!~"up|scrape_.*"}')
            assert not query('{job="node-emulator",unit="FSPUnit1"}')
        retry(absent)
        healthy_statuses = re.findall(r'^(sts_[a-zA-Z0-9_]+)\{[^\n]*\} ([^\s]+)$', raw, re.MULTILINE)
        assert healthy_statuses and all(float(value)==0 for _,value in healthy_statuses), 'Healthy exporter has nonzero status flags'
        retry(lambda: scalar('count({job="fhs-emulator",__name__=~"sts_.*"})', len(healthy_statuses)*len(present)))
        def healthy_flags():
            flags = query('{job="fhs-emulator",__name__=~"sts_.*"} != 0')
            assert len(flags) == 1, flags
            labels = flags[0]['metric']
            assert (labels['__name__'], labels['unit'], labels['fhs'], labels['source']) == ('sts_psu1_fan', 'FSPUnit2', 'FHS1', 'PSU1'), labels
            assert float(flags[0]['value'][1]) == 1
        retry(healthy_flags)
        retry(lambda: scalar('count(sts_psu1_fan{job="fhs-emulator"} == 1)', 1))
        retry(lambda: scalar('sts_psu1_fan{job="fhs-emulator",unit="FSPUnit2",fhs="FHS1"}', 1))
        retry(lambda: scalar('count(sts_psu1_fan{job="fhs-emulator"} == 0)', len(present)-1))
        retry(lambda: scalar('count(node_network_info{job="node-emulator"})', len(present)*2))
        node_interfaces=query('node_network_info{job="node-emulator"}')
        actual_node={(r['metric']['fhs_name'],r['metric']['device']):
                     (r['metric']['address'],r['metric']['ifalias'],r['metric']['unit'],r['metric']['fhs'])
                     for r in node_interfaces}
        expected_node={(h['name'],i['node_device']):
                       (i['node_mac'],i['switch']+':'+i['switch_port'],h['unit'],h['fhs'])
                       for h in present for i in h['interfaces']}
        assert len(node_interfaces)==len(expected_node) and actual_node==expected_node, 'Node MAC/interface associations disagree with topology'
        expected_neighbors = sum(len(sw['links']) for sw in t['switches'])
        retry(lambda: scalar('count(nexus_lldp_id)', expected_neighbors))
        retry(lambda: scalar('count(nexus_interfaces_vdcId{operSt="down"})', 2))
        retry(lambda: scalar('count(nexus_interfaces_vdcId{operSt="up"})', expected_neighbors-2))
        down = [('VCCUnit1-switch','eth1/1/3','FSPUnit3-switch','eth1/1/1'),('FSPUnit3-switch','eth1/1/1','VCCUnit1-switch','eth1/1/3')]
        for source,local,neighbor,remote in down:
            retry(lambda: scalar('nexus_interfaces_vdcId{source='+json.dumps(source)+',interface='+json.dumps(local)+',operSt="down"}',1))
            retry(lambda: scalar('nexus_lldp_id{source='+json.dumps(source)+',interface='+json.dumps(local)+',sysName='+json.dumps(neighbor)+',portIdV='+json.dumps(remote)+'}',1))
        # Compare every neighbor's labels against the fixture, not just totals.
        result=query('nexus_lldp_id')
        actual={(r['metric']['source'],r['metric']['interface']):(r['metric']['sysName'],r['metric']['portIdV'],r['metric']['chassisIdV'],r['metric']['mgmtIp']) for r in result}
        expected={(sw['name'],l['local_port']):(l['neighbor']['name'],l['remote_port'],l['neighbor']['chassis_mac'],l['neighbor']['management_ip']) for sw in t['switches'] for l in sw['links']}
        assert len(result)==len(expected) and actual==expected, 'LLDP neighbor labels disagree with canonical topology'
        states=query('nexus_interfaces_vdcId')
        actual_states={(r['metric']['source'],r['metric']['interface']):r['metric']['operSt'] for r in states}
        expected_states={(sw['name'],l['local_port']):l['state'] for sw in t['switches'] for l in sw['links']}
        assert len(states)==len(expected_states) and actual_states==expected_states, 'Interface states disagree with canonical topology'
        cardinality=query('count({job=~"fhs-emulator|node-emulator"})')
        switch_cardinality=query('count({__name__=~"nexus_.*"})')
        print('Observed cardinality: FHS/node='+json.dumps(cardinality)+'; Cisco='+json.dumps(switch_cardinality), flush=True)
        assert 'nexus_lldp_id' in get(telegraf,'/metrics')
        print(f"PASS actual Cisco MDT -> Telegraf -> Prometheus: {len(t['hosts'])} FHS identities, {len(t['switches'])} switches, {len(t['mesh_links'])} mesh edges; exactly one PSU fault, four NoData hosts and one bidirectional failed link", flush=True)

if __name__ == '__main__':
    main()
