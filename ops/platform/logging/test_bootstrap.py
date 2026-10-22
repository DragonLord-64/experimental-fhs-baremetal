"""Scoped bootstrap requests use fake transport, never a real Elasticsearch."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).parent))
import bootstrap


class BootstrapTest(unittest.TestCase):
    def run_bootstrap(self, existing_role=None):
        calls = []
        def fake(url, password, method, path, body=None):
            self.assertEqual(url, 'http://127.0.0.1:12345')
            calls.append((method, path, body))
            if method == 'PUT':
                return {'acknowledged': True}
            if path == '/':
                return {'version': {'number': '9.5.5'}}
            if path == '/_security/role/filebeat_writer' and existing_role is not None:
                return {'filebeat_writer': existing_role}
            raise urllib.error.HTTPError(url, 404, 'missing', {}, None)
        with tempfile.TemporaryDirectory() as directory:
            credentials = Path(directory) / 'private.json'
            credentials.write_text(json.dumps({'elasticsearch_url': 'http://127.0.0.1:12345',
                                'bootstrap_password': 'synthetic', 'filebeat_password': 'synthetic-publisher'}))
            credentials.chmod(0o600)
            with patch.object(bootstrap, 'api', fake), patch.object(sys, 'argv', ['bootstrap', '--credentials', str(credentials)]):
                with contextlib.redirect_stdout(io.StringIO()):
                    bootstrap.main()
        return calls

    def test_only_scoped_bootstrap_no_documents(self):
        calls = self.run_bootstrap()
        writes = [(path, body) for method, path, body in calls if method == 'PUT']
        self.assertEqual({path for path, _ in writes}, {
            '/_security/role/filebeat_writer', '/_security/user/filebeat_writer',
            '/_ilm/policy/' + bootstrap.NAME, '/_index_template/' + bootstrap.NAME,
            '/' + bootstrap.NAME + '-000001'})
        role = dict(writes)['/_security/role/filebeat_writer']
        self.assertEqual(role['indices'][0]['names'], [bootstrap.NAME, bootstrap.NAME + '-*'])
        self.assertEqual(role['indices'][0]['privileges'], ['auto_configure', 'create_doc'])
        self.assertFalse(any('_doc' in path or '_bulk' in path for _, path, _ in calls))

    def test_reject_overprivileged_existing_writer(self):
        with self.assertRaises(AssertionError):
            self.run_bootstrap({'cluster': ['all'], 'indices': []})


if __name__ == '__main__':
    unittest.main()
