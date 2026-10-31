"""Render the delivered chart and provisioning values and inspect effective config.

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

    def test_provisioning_values_render_active_inventory_plugin(self):
        self.assert_inventory_config(config(render(CHART, '-f', str(ROOT / 'platform/values-provisioning.yaml'))))


if __name__ == '__main__':
    unittest.main()
