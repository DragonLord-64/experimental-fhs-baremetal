"""Offline contract checks; live ingest is a separate supervisor gate."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('fixture', Path(__file__).with_name('fixture.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class FixtureTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = fixture.generate(self.root, 'test-run', 0)

    def response(self):
        docs = [json.loads(line) for line in self.source.read_text().splitlines()]
        for doc in docs:
            doc['log']['level'] = dict(fixture.LEVELS_BY_PRIORITY)[doc['log']['syslog']['priority']]
        return {'hits': {'total': {'value': len(docs), 'relation': 'eq'},
                         'hits': [{'_source': doc} for doc in docs]}}

    def test_bounded_append_and_exclusive_initial_batch(self):
        with self.assertRaises(FileExistsError):
            fixture.generate(self.root, 'test-run', 0)
        with self.assertRaises(ValueError):
            fixture.generate(self.root, 'second-run', 0)
        fixture.generate(self.root, 'test-run', 1)
        with self.assertRaises(ValueError):
            fixture.generate(self.root, 'test-run', 1)
        self.assertLess(self.source.stat().st_size, 8192)
        fixture.verify(self.source, self.response(), 'test-run', 6)

    def test_invalid_identity_and_missing_initial_batch(self):
        for run in ('../escape', 'UPPER', '', 'a' * 65):
            with self.assertRaises(ValueError):
                fixture.generate(self.root, run, 0)
        with self.assertRaises(FileNotFoundError):
            fixture.generate(self.root / 'empty', 'missing', 1)

    def test_exact_contract_and_corruptions(self):
        response = self.response()
        fixture.verify(self.source, response, 'test-run', 3)
        for path, value in [(('host', 'name'), 'second-host'),
                            (('log', 'level'), 'debug'),
                            (('event', 'id'), 'wrong'),
                            (('service', 'name'), 'wrong'),
                            (('process', 'pid'), 2),
                            (('event', 'original'), 'lost'),
                            (('labels', 'test_run'), 'other')]:
            bad = copy.deepcopy(response)
            bad['hits']['hits'][0]['_source'][path[0]][path[1]] = value
            with self.assertRaises(AssertionError, msg=str(path)):
                fixture.verify(self.source, bad, 'test-run', 3)
        for change in ('duplicate', 'timestamp', 'total', 'truncated'):
            bad = copy.deepcopy(response)
            if change == 'duplicate':
                bad['hits']['hits'][1] = bad['hits']['hits'][0]
            elif change == 'timestamp':
                bad['hits']['hits'][0]['_source']['@timestamp'] = '2020-01-01T00:00:00Z'
            elif change == 'total':
                bad['hits']['total']['relation'] = 'gte'
            else:
                bad['hits']['hits'].pop()
            with self.assertRaises(AssertionError, msg=change):
                fixture.verify(self.source, bad, 'test-run', 3)

    def test_overlay_preserves_role_priority_processor(self):
        import yaml
        overlay = yaml.safe_load(Path(__file__).with_name('filebeat.yml').read_text())
        role = (Path(__file__).resolve().parents[3] / 'roles/filebeat/templates/filebeat.yml.j2').read_text()
        processor = overlay['processors'][0]['script']['source']
        for line in processor.strip().splitlines():
            self.assertIn(line.strip(), role)
        self.assertEqual(overlay['output.elasticsearch']['username'], 'filebeat_writer')
        self.assertEqual(overlay['filebeat.inputs'][0]['type'], 'filestream')
        self.assertEqual(overlay['output.elasticsearch']['index'], 'filebeat-fhs-one-9.5.5')


if __name__ == '__main__':
    unittest.main()
