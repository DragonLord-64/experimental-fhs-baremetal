#!/usr/bin/env python3
"""Independent semantic acceptance check for candidate Helm render files."""
import argparse
import json
import sys
from pathlib import Path
import yaml


def check(paths, namespace, hostname, prefix="/test"):
    prefix = prefix.rstrip("/")
    expected_routes = {prefix + "/" + app for app in ["netbox", "grafana", "mid-cbf-kibana"]}
    objects = [obj for path in paths for obj in yaml.safe_load_all(Path(path).read_text()) if obj]
    errors = []
    cluster_kinds = {'ClusterRole', 'ClusterRoleBinding', 'CustomResourceDefinition', 'PersistentVolume', 'StorageClass', 'Namespace', 'IngressClass', 'MutatingWebhookConfiguration', 'ValidatingWebhookConfiguration'}
    services = {o['metadata']['name']: o for o in objects if o.get('kind') == 'Service'}
    routes = set()
    for obj in objects:
        kind = obj.get('kind')
        name = obj.get('metadata', {}).get('name', '?')
        label = f'{kind}/{name}'
        if kind in cluster_kinds:
            errors.append(f'{label}: cluster-scoped resource')
        if obj.get('metadata', {}).get('namespace', namespace) != namespace:
            errors.append(f'{label}: wrong namespace')
        if kind == 'Service' and obj.get('spec', {}).get('type', 'ClusterIP') != 'ClusterIP':
            errors.append(f'{label}: external service exposure')
        if '"hostPath"' in json.dumps(obj):
            errors.append(f'{label}: hostPath volume')
        if kind != 'Ingress':
            continue
        annotations = obj.get('metadata', {}).get('annotations', {})
        if 'nginx.ingress.kubernetes.io/rewrite-target' in annotations:
            errors.append(f'{label}: inherited rewrite annotation')
        if obj['spec'].get('ingressClassName') != 'nginx':
            errors.append(f'{label}: wrong ingress class')
        for rule in obj['spec'].get('rules', []):
            if rule.get('host') != hostname:
                errors.append(f'{label}: wrong ingress host')
            for path in rule.get('http', {}).get('paths', []):
                route = path['path'].rstrip('/')
                routes.add(route)
                if route not in expected_routes:
                    errors.append(f'{label}: non-candidate route {route}')
                if path.get('pathType') != 'Prefix':
                    errors.append(f'{label}: route is not Prefix')
                backend = path['backend']['service']
                service = services.get(backend['name'])
                if service is None:
                    errors.append(f'{label}: missing service {backend["name"]}')
                elif not any(p.get('port') == backend['port'].get('number') or p.get('name') == backend['port'].get('name') for p in service['spec']['ports']):
                    errors.append(f'{label}: backend port missing')
    for route in expected_routes - routes:
        errors.append(f'missing browser route {route}')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+')
    parser.add_argument('--namespace', default='mid-cbf-monitoring-test')
    parser.add_argument('--hostname', default='rmdskadevdu011.mda.ca')
    parser.add_argument('--prefix', default='/test')
    args = parser.parse_args()
    errors = check(args.paths, args.namespace, args.hostname, args.prefix)
    print('\n'.join(errors) if errors else 'candidate manifest acceptance passed')
    sys.exit(bool(errors))
