"""Finite repair-script checks; no package/network/service changes."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('environment_patch', ROOT/'scripts/patch-bifrost-environment.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PatchTest(unittest.TestCase):
    def test_diagnose_reports_failed_import_without_updates(self):
        with patch.object(module, 'metadata', return_value={'python':'3.12', 'packages':{}}), \
             patch.object(module.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 1)]) as calls:
            self.assertEqual(1, module.diagnose(Path(sys.executable)))
            self.assertEqual(2, calls.call_count)

    def test_import_probe_detects_gen_email_error_and_keeps_running(self):
        import io
        real_import = __import__('importlib').import_module
        def broken(name):
            if name == 'OpenSSL.crypto':
                raise AttributeError("module 'lib' has no attribute 'GEN_EMAIL'")
            if name in ('eventlet', 'oslo_service.backend', 'ironic.cmd.dbsync'):
                return object()
            return real_import(name)
        output = io.StringIO()
        with patch('importlib.import_module', side_effect=broken), patch('sys.stdout', output):
            with self.assertRaises(SystemExit) as result:
                exec(module.IMPORTS, {})
        self.assertEqual(1, result.exception.code)
        self.assertIn('GEN_EMAIL', output.getvalue())
        self.assertIn('PASS import ironic.cmd.dbsync', output.getvalue())

    def test_snapshot_has_private_mode_and_only_versions(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(module, 'metadata', return_value={'packages':{'certifi':'old'}}):
            module.snapshot(Path(sys.executable), Path(folder))
            file = next(Path(folder).glob('*.json'))
            self.assertEqual(0o600, file.stat().st_mode & 0o777)
            self.assertEqual({'packages':{'certifi':'old'}}, json.loads(file.read_text()))

    def test_repair_requires_constraints_before_mutation(self):
        with patch.object(sys, 'argv', ['script', 'repair-openssl', '--python', sys.executable]), patch.object(module, 'snapshot') as save:
            with self.assertRaises(SystemExit) as result:
                module.main()
            self.assertEqual(2, result.exception.code)
            save.assert_not_called()

    def test_update_stops_if_bootstrap_fails_without_touching_openssl(self):
        commands = []
        def failing(argv, **kwargs):
            commands.append([str(a) for a in argv])
            if 'pip @ ' + module.PIP_WHEEL in argv:
                raise subprocess.CalledProcessError(1, argv)
        with patch.object(sys, 'argv', ['script', 'update', '--python', sys.executable]), \
             patch.object(module.os, 'geteuid', return_value=0), \
             patch.object(module.Path, 'is_file', return_value=True), \
             patch.object(module, 'snapshot'), patch.object(module, 'run', side_effect=failing):
            with self.assertRaises(subprocess.CalledProcessError):
                module.main()
        self.assertFalse(any('pyOpenSSL' in cmd or 'certifi>=2026.10.19' in cmd for cmd in commands))
        self.assertTrue(commands[-1][-1].endswith('sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'))


if __name__ == '__main__':
    unittest.main()
