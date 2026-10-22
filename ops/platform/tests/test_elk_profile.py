"""Offline chart rendering: paused lab survives redeploy; resume is reversible."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
import yaml
import jsonschema

ROOT = Path(__file__).resolve().parents[3]
CHART = ROOT / 'platform/charts/elasticsearch-kibana'
LAB = ROOT / 'ops/platform/monitoring-values/elasticsearch.yaml'

class ElkProfile(unittest.TestCase):
    def test_replica_schema(self):
        schema = json.loads((CHART / 'values.schema.json').read_text())
        values = yaml.safe_load((CHART / 'values.yaml').read_text())
        for count in (0, 1):
            for name in ('elasticsearch', 'kibana'):
                values[name]['replicas'] = count
            jsonschema.validate(values, schema)
        for invalid in (-1, 2, '0', False):
            values['elasticsearch']['replicas'] = invalid
            with self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate(values, schema)

    def test_paused_and_resumed_manifests(self):
        helm = shutil.which('helm')
        if not helm:
            self.skipTest('helm unavailable')
        args = [helm, 'template', 'elastic', str(CHART), '-f', str(LAB)]
        def render(extra):
            return list(yaml.safe_load_all(subprocess.check_output(args + extra, text=True)))
        paused = render([])
        resumed = render(['--set', 'elasticsearch.replicas=1,kibana.replicas=1'])
        for docs, count in ((paused, 0), (resumed, 1)):
            workloads = [d for d in docs if d and d['kind'] in ('Deployment','StatefulSet')]
            self.assertEqual(len(workloads), 2)
            self.assertTrue(all(d['spec']['replicas'] == count for d in workloads))
        self.assertFalse(any(d and d['kind'] == 'Job' for d in paused))
        self.assertTrue(any(d and d['kind'] == 'Job' for d in resumed))
        claims = lambda docs: next(d['spec']['volumeClaimTemplates'] for d in docs if d and d['kind']=='StatefulSet')
        self.assertEqual(claims(paused), claims(resumed))
        self.assertEqual(claims(paused)[0]['spec']['storageClassName'], 'fhs-retain')
