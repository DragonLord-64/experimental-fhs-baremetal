"""Offline rendered contracts for the public-image Topology Views installation."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT/'platform/charts/fhs-platform'
PIN = 'netbox-topology-views==5.0.0 --hash=sha256:afe03396b67e8ed16ae2ad43d13bd8380f48cc0ffd1621259b6a60fa21f7170f'


class TopologyChart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(['helm', 'template', 'mid-cbf-hw', str(CHART),
            '--namespace', 'fhs-discovery-portal-test', '--set-string', 'global.urlPrefix=/mid-cbf-hw'],
            capture_output=True, check=True)
        cls.objects = [o for o in yaml.safe_load_all(result.stdout) if o]

    def test_all_consumers_install_hash_pinned_plugin_and_writable_static(self):
        consumers = []
        for obj in self.objects:
            if obj['kind'] == 'Deployment' and obj['metadata']['name'].startswith('fhs-netbox'):
                consumers.append(obj['spec']['template']['spec'])
            if obj['kind'] == 'CronJob' and obj['metadata']['name'].startswith('fhs-netbox'):
                consumers.append(obj['spec']['jobTemplate']['spec']['template']['spec'])
        self.assertEqual(len(consumers), 3)
        for spec in consumers:
            init = next(c for c in spec['initContainers'] if c['name']=='install-inventory-plugin')
            script = init['command'][-1]
            self.assertIn(PIN, script)
            self.assertIn('--no-deps --require-hashes', script)
            self.assertIn('mkdir -p /plugin-static/netbox_topology_views/img', script)
            self.assertIn('ghcr.io/netbox-community/netbox@sha256:', init['image'])
            container = spec['containers'][0]
            static = next(m for m in container['volumeMounts'] if m['mountPath']=='/opt/netbox/netbox/static')
            self.assertFalse(static.get('readOnly', False))
            self.assertTrue(any(v['name']==static['name'] and 'emptyDir' in v for v in spec['volumes']))
            self.assertIn('PYTHONPATH=/opt/netbox/plugin-packages', ' '.join(container['command']))
        web = next(o for o in self.objects if o['kind']=='Deployment' and o['metadata']['name']=='fhs-netbox')
        self.assertIn('collectstatic --no-input', ' '.join(web['spec']['template']['spec']['containers'][0]['command']))

    def test_rendered_configuration_and_optional_recipe_match(self):
        configs = [o for o in self.objects if o['kind']=='ConfigMap' and 'netbox_topology_views' in str(o.get('data'))]
        self.assertTrue(configs)
        self.assertIn('netbox_topology_views', str(configs))
        self.assertIn(PIN, (CHART/'netbox-image/requirements.txt').read_text())
        self.assertIn('netbox_topology_views', (CHART/'netbox-image/plugins.py').read_text())
        self.assertIn('mkdir -p /opt/netbox/netbox/static/netbox_topology_views/img',
                      (CHART/'netbox-image/Dockerfile').read_text())

    def test_smoke_scope_rejects_other_clusters(self):
        spec = importlib.util.spec_from_file_location('smoke', Path(__file__).with_name('smoke.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with self.assertRaises(ValueError):
            module.lab.validate_scope('monitoring', 'fhs-discovery-portal-test')
        with self.assertRaises(ValueError):
            module.lab.validate_scope('fhs-test', 'fhs-platform')


if __name__ == '__main__':
    unittest.main()
