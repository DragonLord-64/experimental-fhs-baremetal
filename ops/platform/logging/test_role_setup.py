"""Delegated role setup with a synthetic Debian package; no Elasticsearch writes."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which('ansible-playbook') and shutil.which('dpkg-deb'),
                     'requires ansible-playbook and dpkg-deb')
class SetupTest(unittest.TestCase):
    def test_delegation_authentication_and_failure_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'package'
            (package / 'DEBIAN').mkdir(parents=True)
            (package / 'DEBIAN/control').write_text(
                'Package: filebeat\nVersion: 9.5.5\nArchitecture: amd64\n'
                'Maintainer: Test <test@example.invalid>\nDescription: fixture\n')
            binary = package / 'usr/share/filebeat/bin/filebeat'
            binary.parent.mkdir(parents=True)
            marker = root / 'called'
            binary.write_text('#!/usr/bin/env python3\n'
                              'import pathlib, sys, yaml\n'
                              'assert sys.argv[1:3] == ["setup", "--index-management"]\n'
                              'p = pathlib.Path(sys.argv[sys.argv.index("-c") + 1])\n'
                              'assert p.stat().st_mode & 0o777 == 0o600\n'
                              'c = yaml.safe_load(p.read_text())\n'
                              'assert c["setup.ilm.check_exists"] is True\n'
                              'o = c["output.elasticsearch"]\n'
                              'assert o.get("api_key") == "fixture:key" or '
                              '(o.get("username"), o.get("password")) == ("setup", "fixture")\n'
                              f'pathlib.Path({str(marker)!r}).write_text(str(p.parent))\n'
                              f'sys.exit(1 if pathlib.Path({str(root / "fail")!r}).exists() else 0)\n')
            binary.chmod(0o755)
            deb = root / 'filebeat.deb'
            subprocess.run(['dpkg-deb', '--build', str(package), str(deb)], check=True,
                           stdout=subprocess.DEVNULL)
            credentials = root / 'credentials.yml'
            play = root / 'play.yml'
            play.write_text(yaml.safe_dump([{
                'hosts': 'devices', 'gather_facts': False,
                'vars': {'filebeat_setup_enabled': True,
                         'filebeat_setup_delegate': 'localhost',
                         'filebeat_package_path': str(deb),
                         'filebeat_setup_credentials_file': str(credentials),
                         'filebeat_elasticsearch_hosts': ['https://example.invalid:9200'],
                         'filebeat_ssl_verification_mode': 'full',
                         'filebeat_setup_ssl_certificate_authorities': []},
                'tasks': [{'ansible.builtin.import_role': {'name': str(ROOT / 'roles/filebeat'), 'tasks_from': 'setup'},
                           'delegate_to': '{{ filebeat_setup_delegate }}',
                           'become': False, 'run_once': True,
                           'when': 'filebeat_setup_enabled | bool and not ansible_check_mode'}]}]))
            inventory = root / 'inventory'
            inventory.write_text('[devices]\nunreachable-device ansible_connection=ssh\n'
                                 '[all:vars]\nansible_remote_tmp=/tmp/fhs-filebeat-ansible\nansible_python_interpreter=' + shutil.which('python3') + '\n')
            command = ['ansible-playbook', '-i', str(inventory), str(play)]
            for api_key, fail in [(True, False), (False, True)]:
                credentials.write_text(yaml.safe_dump(
                    {'filebeat_elasticsearch_api_key': 'fixture:key'} if api_key else
                    {'filebeat_elasticsearch_username': 'setup',
                     'filebeat_elasticsearch_password': 'fixture'}))
                if fail:
                    (root / 'fail').touch()
                result = subprocess.run(command, capture_output=True, text=True,
                                        env={**os.environ, 'ANSIBLE_LOCAL_TEMP': str(root / 'ansible')})
                self.assertEqual(result.returncode == 0, not fail, result.stdout + result.stderr)
                self.assertFalse(Path(marker.read_text()).exists(), 'setup workspace leaked')
                self.assertNotIn('fixture:key', result.stdout)
            marker.unlink()
            result = subprocess.run(command + ['--check'], capture_output=True, text=True,
                                    env={**os.environ, 'ANSIBLE_LOCAL_TEMP': str(root / 'ansible')})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
