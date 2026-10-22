import contextlib
import importlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
reload = importlib.import_module('reload')


class ReloadContracts(unittest.TestCase):
    def exercise(self, mounted=None, loaded=None, status=200):
        desired = 'scrape_configs:\n- job_name: existing\n- job_name: fhs-emulator\n  static_configs:\n  - targets: [cache:9110]\n    labels: {unit: VCCUnit1}\n- job_name: node-emulator\n'
        cm = json.dumps({'data': {'prometheus.yml': desired}}).encode()
        response = MagicMock()
        response.__enter__.return_value.status = status
        with patch.object(reload.subprocess, 'check_output', side_effect=[cm, (mounted or desired).encode()]), \
             patch.object(reload, 'retry', side_effect=lambda fn, seconds: fn()), \
             patch.object(reload, 'forward', return_value=contextlib.nullcontext(12345)), \
             patch.object(reload, 'get', return_value=json.dumps({'status': 'success', 'data': {'yaml': loaded or desired}})), \
             patch.object(reload.urllib.request, 'urlopen', return_value=response) as post:
            try:
                reload.reload_config()
            finally:
                self.post = post

    def test_reload_after_projection_and_check_loaded_jobs(self):
        self.exercise()
        request = self.post.call_args.args[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.full_url, 'http://127.0.0.1:12345/-/reload')
        self.assertEqual(reload.job_names('  - job_name: "fhs-emulator"\n  - job_name: \'node-emulator\'\n'), {'fhs-emulator', 'node-emulator'})

    def test_stale_projection_does_not_reload(self):
        with self.assertRaisesRegex(RuntimeError, 'projected ConfigMap'):
            self.exercise(mounted='scrape_configs:\n- job_name: existing\n')
        self.post.assert_not_called()

    def test_stale_loaded_jobs_fail_even_with_healthy_server(self):
        with self.assertRaisesRegex(RuntimeError, 'loaded scrape jobs differ'):
            self.exercise(loaded='scrape_configs:\n- job_name: existing\n')

    def test_same_jobs_with_stale_inventory_fail(self):
        with self.assertRaisesRegex(RuntimeError, 'static targets/labels differ'):
            self.exercise(loaded='scrape_configs:\n- job_name: existing\n- job_name: fhs-emulator\n  static_configs:\n  - targets: [cache:9110]\n    labels: {unit: VCCUnit24}\n- job_name: node-emulator\n')

    def test_rejected_reload_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'rejected'):
            self.exercise(status=500)


if __name__ == '__main__':
    unittest.main()
