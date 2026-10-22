#!/usr/bin/env python3
"""Render the isolated monitoring fixtures as Kubernetes JSON."""
import json
from pathlib import Path
import sys
from fixture import node_metrics
from topology import configured

ROOT = Path(__file__).resolve().parent
NAMESPACE = 'fhs-emulators'
LABELS = {'app.kubernetes.io/part-of': 'fhs-emulators'}

def metadata(name, labels=None):
    return {'name': name, 'namespace': NAMESPACE, 'labels': {**LABELS, **(labels or {})}}

def security():
    return {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True,
            'capabilities': {'drop': ['ALL']}}

def render():
    pins = json.loads((ROOT / 'images.json').read_text())
    t = configured()
    objects = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE, 'labels': LABELS}},
        {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': metadata('monitoring-fixtures'),
         'data': {'topology.json': json.dumps(t, separators=(',', ':')), 'node.prom': node_metrics(t), **{p.name: p.read_text() for p in sorted((ROOT / 'fixtures').glob('fhstelemetry-*.yaml'))}}}]
    fhs = {'name': 'fhs', 'image': pins['fhs'],
           'command': ['/app/bin/fhs-prometheus-exporter'],
           'args': ['--emulation_mode', '--fpga_card_names', 'shared-fpga0,shared-fpga1', '--port', '9110'],
           'volumeMounts': [{'name': 'fixtures', 'mountPath': '/app/mnt/config', 'readOnly': True}],
           'ports': [{'name': 'fhs-metrics', 'containerPort': 9110}],
           'resources': {'requests': {'cpu': '10m', 'memory': '128Mi'}, 'limits': {'cpu': '250m', 'memory': '192Mi'}},
           'securityContext': security(),
           'readinessProbe': {'httpGet': {'path': '/metrics', 'port': 9110}, 'periodSeconds': 10}}
    fault = json.loads(json.dumps(fhs))
    fault['name'] = 'fhs-psu1-fault'
    fault['args'][-1] = '9111'
    fault['args'] += ['--ipmi_emulation_metrics_filepath', '/app/mnt/config/fhstelemetry-ipmi-psu1-fault.yaml']
    fault['ports'] = [{'name': 'fault-metrics', 'containerPort': 9111}]
    fault['readinessProbe']['httpGet']['port'] = 9111
    node = {'name': 'node', 'image': pins['node'],
            'args': ['--collector.disable-defaults', '--collector.textfile', '--collector.textfile.directory=/fixtures', '--web.listen-address=:9100'],
            'ports': [{'name': 'node-metrics', 'containerPort': 9100}],
            'volumeMounts': [{'name': 'fixtures', 'mountPath': '/fixtures', 'readOnly': True}],
            'resources': {'requests': {'cpu': '5m', 'memory': '32Mi'}, 'limits': {'cpu': '100m', 'memory': '64Mi'}},
            'securityContext': security(),
            'readinessProbe': {'httpGet': {'path': '/metrics', 'port': 9100}, 'periodSeconds': 10}}
    sender = {'name': 'cisco', 'image': pins['cisco'], 'imagePullPolicy': 'Never',
              'args': ['--topology=/fixtures/topology.json'],
              'volumeMounts': [{'name': 'fixtures', 'mountPath': '/fixtures', 'readOnly': True}],
              'resources': {'requests': {'cpu': '5m', 'memory': '32Mi'}, 'limits': {'cpu': '100m', 'memory': '64Mi'}},
              'securityContext': security()}
    for name, containers in [('fhs-emulator', [fhs, fault, node]), ('cisco-emulator', [sender])]:
        labels = {'app': name}
        objects.append({'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': metadata(name),
            'spec': {'replicas': 1, 'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': labels},
                     'template': {'metadata': {'labels': {**LABELS, **labels}}, 'spec': {
                         'automountServiceAccountToken': False,
                         'securityContext': {'runAsNonRoot': True, 'runAsUser': 65532, 'runAsGroup': 65532, 'seccompProfile': {'type': 'RuntimeDefault'}},
                         'containers': containers,
                         'volumes': [{'name': 'fixtures', 'configMap': {'name': 'monitoring-fixtures'}}]}}}})
    objects.append({'apiVersion': 'v1', 'kind': 'Service', 'metadata': metadata('fhs-emulator'),
        'spec': {'type': 'ClusterIP', 'selector': {'app': 'fhs-emulator'},
                 'ports': [{'name': 'fhs-metrics', 'port': 9110, 'targetPort': 9110}, {'name': 'fault-metrics', 'port': 9111, 'targetPort': 9111}, {'name': 'node-metrics', 'port': 9100, 'targetPort': 9100}]}})
    return {'apiVersion': 'v1', 'kind': 'List', 'items': objects}

if __name__ == '__main__':
    json.dump(render(), sys.stdout, indent=2)
    print()
