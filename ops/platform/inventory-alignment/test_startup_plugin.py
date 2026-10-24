"""Check actual startup wiring and failure behavior for registry-free plugin installation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_deployment import render, CHART


class StartupPluginTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.objects=render(CHART)
        cls.pods={o['metadata']['name']:(o['spec']['jobTemplate']['spec']['template']['spec'] if o['kind']=='CronJob' else o['spec']['template']['spec'])
                  for o in cls.objects if o['kind'] in ('Deployment','CronJob') and o['metadata']['name'] in ('fhs-netbox','fhs-netbox-worker','fhs-netbox-housekeeping')}

    def test_every_consumer_installs_and_loads_pinned_plugin_as_nonroot(self):
        self.assertEqual(3,len(self.pods))
        scripts=[]
        for name,pod in self.pods.items():
            container=pod['containers'][0]
            self.assertIn('ghcr.io/netbox-community/netbox@sha256:',container['image'])
            init=next(c for c in pod['initContainers'] if c['name']=='install-inventory-plugin')
            self.assertEqual(container['image'],init['image'])
            self.assertEqual(1000,init['securityContext']['runAsUser'])
            self.assertTrue(init['securityContext']['readOnlyRootFilesystem'])
            script=init['command'][-1]; scripts.append(script)
            self.assertIn('netbox-inventory==2.7.1 --hash=sha256:',script)
            self.assertIn('--require-hashes',script)
            self.assertIn('--no-deps',script)
            self.assertEqual(['/usr/bin/env','PYTHONPATH=/opt/netbox/plugin-packages'],container['command'][:2])
            self.assertIn({'configMapRef': {'name': 'fhs-netbox-plugin-environment'}},container['envFrom'])
            volumes={v['name'] for v in pod['volumes'] if 'emptyDir' in v}
            self.assertTrue({'inventory-plugin-packages','inventory-plugin-static'} <= volumes)
            self.assertEqual({'/opt/netbox/plugin-packages','/opt/netbox/netbox/static'},
                {m['mountPath'] for m in container['volumeMounts'] if m['name'].startswith('inventory-plugin-')})
        self.assertEqual(1,len(set(scripts)))

    def run_installer(self,present=False,fail=False):
        init=next(c for c in self.pods['fhs-netbox']['initContainers'] if c['name']=='install-inventory-plugin')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); packages=root/'packages'; packages.mkdir(); static=root/'static';static.mkdir(); source=root/'source';source.mkdir()
            (source/'netbox.css').write_text('base asset')
            python=root/'python';python.write_text('#!/bin/sh\nexit '+('0' if present else '1')+'\n');python.chmod(0o700)
            uv=root/'uv';marker=root/'installed';uv.write_text('#!/bin/sh\nprintf called > "'+str(marker)+'"\nexit '+('1' if fail else '0')+'\n');uv.chmod(0o700)
            script=init['command'][-1].replace('/opt/netbox/venv/bin/python',str(python)).replace('/usr/local/bin/uv',str(uv)).replace('/plugin-packages',str(packages)).replace('/plugin-static',str(static)).replace('/opt/netbox/netbox/static',str(source))
            result=subprocess.run(['/bin/sh','-ec',script],capture_output=True,text=True)
            return result.returncode,marker.exists(),(static/'netbox.css').exists()

    def test_stock_image_installs_package_and_preserves_base_assets(self):
        self.assertEqual((0,True,True),self.run_installer())

    def test_prebuilt_image_keeps_offline_install_path(self):
        self.assertEqual((0,False,True),self.run_installer(present=True))

    def test_package_failure_stops_startup(self):
        self.assertEqual((1,True,False),self.run_installer(fail=True))
