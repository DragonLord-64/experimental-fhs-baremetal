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
        from types import SimpleNamespace
        entry = SimpleNamespace(group='console_scripts', name='ironic-dbsync',
            value='ironic.command.dbsync:main', load=lambda: object())
        with patch('importlib.import_module', side_effect=broken), patch('sys.stdout', output), \
             patch('importlib.metadata.distribution', return_value=SimpleNamespace(entry_points=[entry])):
            with self.assertRaises(SystemExit) as result:
                exec(module.IMPORTS, {})
        self.assertEqual(1, result.exception.code)
        self.assertIn('GEN_EMAIL', output.getvalue())
        self.assertIn('PASS ironic-dbsync entry point: ironic.command.dbsync:main', output.getvalue())

    def test_duplicate_metadata_reports_active_distribution(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for name, version in [('active', '2026.10.23'), ('fallback', '2023.11.17')]:
                site = Path(folder)/name
                metadata = site/('certifi-' + version + '.dist-info')
                metadata.mkdir(parents=True)
                (metadata/'METADATA').write_text('Name: certifi\nVersion: ' + version + '\n')
                paths.append(str(site))
            probe = 'import sys; sys.path[:0] = ' + repr(paths) + '\n' + module.METADATA
            result = subprocess.run([sys.executable, '-c', probe], check=True, capture_output=True, text=True)
            info = json.loads(result.stdout)
            self.assertEqual('2026.10.23', info['packages']['certifi'])
            self.assertEqual(paths[0], info['locations']['certifi'])

    def test_snapshot_has_private_mode_and_only_versions(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(module, 'metadata', return_value={'packages':{'certifi':'old'}}):
            module.snapshot(Path(sys.executable), Path(folder))
            file = next(Path(folder).glob('*.json'))
            self.assertEqual(0o600, file.stat().st_mode & 0o777)
            self.assertEqual({'packages':{'certifi':'old'}}, json.loads(file.read_text()))

    def test_repair_requires_constraints_before_mutation(self):
        with patch.object(sys, 'argv', ['script', 'repair-openssl', '--python', sys.executable, '--constraints', '/nonexistent/fhs-constraints.txt']), patch.object(module, 'snapshot') as save:
            with self.assertRaises(SystemExit) as result:
                module.main()
            self.assertEqual(2, result.exception.code)
            save.assert_not_called()

    def test_constraints_skip_broken_link_and_reject_conflicting_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            broken = root/'broken'; broken.symlink_to(root/'missing')
            valid = root/'valid'; valid.write_text('cryptography===43.0.3\n')
            self.assertEqual(valid, module.select_constraints(candidates=[broken, valid]))
            other = root/'other'; other.write_text('cryptography===50.0.2\n')
            with self.assertRaises(ValueError):
                module.select_constraints(candidates=[valid, other])
            with self.assertRaises(ValueError):
                module.select_constraints(candidates=[broken])

    def test_repair_resolves_all_three_packages_together(self):
        with tempfile.TemporaryDirectory() as folder:
            constraints = Path(folder)/'upper-constraints.txt'
            constraints.write_text('cryptography===43.0.3\n')
            with patch.object(sys, 'argv', ['script', 'repair-openssl', '--python', sys.executable]), \
                 patch.object(module.os, 'geteuid', return_value=0), \
                 patch.object(module, 'select_constraints', return_value=constraints), \
                 patch.object(module, 'snapshot'), patch.object(module, 'diagnose', return_value=0), \
                 patch.object(module, 'run') as commands:
                self.assertEqual(0, module.main())
                args = commands.call_args.args[0]
                self.assertEqual(['pyOpenSSL', 'cryptography', 'jwcrypto'], args[-3:])
                self.assertEqual(constraints, args[args.index('--constraint') + 1])
                self.assertEqual(1, commands.call_count)

    def test_configure_refuses_broken_environment_before_install(self):
        with patch.object(sys, 'argv', ['script', 'configure', '--python', sys.executable]), \
             patch.object(module.os, 'geteuid', return_value=0), \
             patch.object(module, 'diagnose', return_value=1), patch.object(module, 'run') as commands:
            self.assertEqual(1, module.main())
            commands.assert_not_called()

    def test_configure_disables_source_and_package_installs(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'install.yaml').write_text('[]')
            with patch.object(sys, 'argv', ['script', 'configure', '--python', sys.executable, '--playbooks', folder]), \
                 patch.object(module.os, 'geteuid', return_value=0), \
                 patch.object(module, 'diagnose', return_value=0), patch.object(module, 'run') as commands:
                self.assertEqual(0, module.main())
                args = commands.call_args.args[0]
                for value in ('skip_install=true', 'skip_package_install=true', 'update_repos=false',
                              'create_image_via_dib=false', 'create_ipa_image=false', 'download_ipa=false'):
                    self.assertIn(value, args)
                self.assertEqual(folder, str(commands.call_args.kwargs['cwd']))

    def test_explicit_image_build_keeps_runtime_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'install.yaml').write_text('[]')
            with patch.object(sys, 'argv', ['script', 'configure', '--build-images', '--python', sys.executable, '--playbooks', folder]), \
                 patch.object(module.os, 'geteuid', return_value=0), \
                 patch.object(module, 'diagnose', return_value=0), patch.object(module, 'run') as commands:
                self.assertEqual(0, module.main())
                args = commands.call_args.args[0]
                self.assertIn('skip_install=true', args)
                self.assertIn('skip_package_install=true', args)
                self.assertNotIn('create_ipa_image=false', args)

    def test_image_constraints_preserve_release_except_trust_updates(self):
        spec = importlib.util.spec_from_file_location('prepare', ROOT/'bifrost-infra/prepare-python-constraints.py')
        prepare = importlib.util.module_from_spec(spec); spec.loader.exec_module(prepare)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'upper-constraints.txt'
            baseline = 'ironic===35.1.1\npyOpenSSL===24.2.1\ncryptography===43.0.3\njwcrypto===1.5.6\n'
            source.write_text(baseline + 'certifi===2026.7.22\npip===26.2.1\n')
            result = prepare.prepare(source)
            self.assertTrue(result.startswith(baseline))
            self.assertNotIn('2026.7.22', result)
            self.assertIn('pip===26.2.2', result)
            self.assertIn('certifi===2026.10.23', result)
            source.write_text('cryptography===43.0.3')
            with self.assertRaises(ValueError):
                prepare.prepare(source)

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
