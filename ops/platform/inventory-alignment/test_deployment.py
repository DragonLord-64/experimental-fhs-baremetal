"""Render the delivered and legacy launch paths and inspect effective config.

These are configuration regressions; real image loading and migrations remain
an isolated-service acceptance requirement in HANDOFF.md.
"""
from pathlib import Path
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / 'platform/charts/fhs-platform'


def render(chart, *options):
    proc = subprocess.run(['helm', 'template', 'inventory-screen', str(chart), '--namespace',
                           'inventory-screen', *options], text=True, capture_output=True, check=True)
    return [o for o in yaml.safe_load_all(proc.stdout) if o]


def config(objects):
    cm = next(o for o in objects if o['kind'] == 'ConfigMap' and 'netbox.yaml' in o.get('data', {}))
    settings = yaml.safe_load(cm['data']['netbox.yaml'])
    for name, text in sorted(cm['data'].items()):
        if name.startswith('extra-') and name.endswith('.yaml'):
            settings.update(yaml.safe_load(text))
    return settings


class DeploymentTest(unittest.TestCase):
    def assert_inventory_config(self, settings):
        self.assertIn('netbox_inventory', settings.get('PLUGINS', []), 'NetBox must load the installed plugin')
        self.assertIs(True, settings.get('PLUGINS_CONFIG', {}).get('netbox_inventory', {}).get('sync_hardware_serial_asset_tag'))
        choices = settings.get('FIELD_CHOICES', {}).get('netbox_inventory.Asset.status+', [])
        self.assertIn(['faulty', 'Faulty / quarantine', 'red'], choices)

    def test_umbrella_renders_active_inventory_plugin(self):
        self.assert_inventory_config(config(render(CHART)))

    def test_legacy_source_and_dragonvm_render_active_inventory_plugin(self):
        # Test canonical standalone values plus the actual lab overlay, rather
        # than reading source YAML keys that the chart may not support.
        chart = CHART / 'charts/netbox-8.3.67.tgz'
        for overlay in ((), ('-f', str(ROOT / 'ops/platform/dragonvm/netbox.yaml'))):
            with self.subTest(overlay=bool(overlay)):
                self.assert_inventory_config(config(render(chart, '-f', str(ROOT / 'platform/netbox.yaml'), *overlay)))


if __name__ == '__main__':
    unittest.main()


class LegacyLauncherTest(unittest.TestCase):
    def test_legacy_launcher_static_route_and_shared_image(self):
        import sys
        sys.path.insert(0,str(ROOT/'ops/platform/umbrella'))
        from test_umbrella import netbox_launch, last_option, pod_specs
        chart=CHART/'charts/netbox-8.3.67.tgz'
        for base in ('netbox/','review/netbox/'):
            objects=render(chart,'-f',str(ROOT/'platform/netbox.yaml'),'-f',str(ROOT/'ops/platform/dragonvm/netbox.yaml'),'--set-string','basePath='+base)
            images=[]
            for obj,pod in pod_specs(objects):
                if obj['kind'] in ('Deployment','CronJob'):
                    images.append(pod['containers'][0]['image'])
                    if obj['kind']=='Deployment' and obj['metadata']['name']=='netbox':
                        launched=netbox_launch(pod['containers'][0])
                        self.assertEqual('/'+base.rstrip('/')+'/static',last_option(launched['args'],'--static-path-route'))
                        self.assertEqual('netbox.granian:application',launched['args'][-1])
            self.assertTrue(images)
            self.assertEqual({'fhs/netbox-inventory:4.7.0-2.7.1'},set(images))
