#!/usr/bin/env python3
"""Read-only supervisor gate. URL must be the disposable fhs-test Prometheus (supervisor-verified tunnel)."""
import argparse
import json
from urllib.parse import urlencode
from urllib.request import urlopen
from exact import inventory, server_status, inventory_fallback, expected_host
from generate import health


def validate(query):
    expected={(p['unit'],p['fhs']) for p in inventory() if p['kind']=='server' and not p['deployed']}
    samples=query('fhs_visual_status{job="node-emulator",origin="visual_fixture"}')
    identities=[(s['metric'].get('unit'),s['metric'].get('fhs')) for s in samples]
    if len(samples)!=116 or set(identities)!=expected or any(float(s['value'][1])!=0 for s in samples):
        raise ValueError('Feed must be exactly 116 unique nonemulated ok statuses')
    for host in (p for p in inventory() if p['kind']=='server'):
        unit,fhs=host['unit'],host['fhs']
        expr=server_status(health(unit,fhs),unit,fhs).replace('$job','fhs')
        samples=query(expr)
        expected_state=0
        if host['deployed']:
            observed=inventory_fallback(health(unit,fhs),expected_host().replace('$unit',unit).replace('$fhs',fhs)).replace('$job','fhs')
            baseline=query(observed)
            if len(baseline)!=1:
                raise ValueError('Expected one observed-only status: '+unit+'/'+fhs)
            expected_state=float(baseline[0]['value'][1])
            scenario=3 if unit=='FSPUnit1' else (1 if (unit,fhs)==('FSPUnit2','FHS1') else None)
            if scenario is not None and expected_state!=scenario:
                raise ValueError('Unexpected observed scenario: '+unit+'/'+fhs)
        if len(samples)!=1 or float(samples[0]['value'][1])!=expected_state:
            raise ValueError('Unexpected server status: '+unit+'/'+fhs)
    return {'fixture_servers':116,'actual_servers':16,'status_queries':132}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--prometheus-url',required=True)
    parser.add_argument('--namespace',required=True,choices=['fhs-test'])
    parser.add_argument('--job',required=True,help='Actual observed FHS job')
    args=parser.parse_args()
    def query(expr):
        expr=expr.replace('job="fhs"','job='+json.dumps(args.job))
        with urlopen(args.prometheus_url.rstrip('/')+'/api/v1/query?'+urlencode({'query':expr}),timeout=20) as response:
            result=json.load(response)
        if result['status']!='success' or result['data']['resultType']!='vector':
            raise ValueError('Prometheus query did not return a successful vector')
        return result['data']['result']
    print(json.dumps(validate(query),sort_keys=True))
