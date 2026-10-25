"""Execute the actual import router with synthetic discovery payloads.

Ansible schedules the real plays/includes, tags, limits, credential override and
connection keywords. Only internal device payloads are replaced with a local
probe; network_cli is a local transport shim. No SSH, NetBox or hardware access.
Run with a real ansible-core installed (otherwise explicitly skipped).
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'playbooks/netbox'


class RoutingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        executable = shutil.which('ansible-playbook')
        if executable:
            cls.command = [executable]
        elif importlib.util.find_spec('ansible'):
            cls.command = [sys.executable, '-m', 'ansible.cli.playbook']
        else:
            raise unittest.SkipTest('Real ansible-core required for synthetic routing execution')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fhs-routing-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        shutil.copyfile(SOURCE / 'defaults.yml', self.folder / 'defaults.yml')
        (self.folder / 'tasks').mkdir()
        (self.folder / 'action_plugins').mkdir()
        (self.folder / 'ansible.cfg').write_text('[defaults]\nretry_files_enabled=False\nstdout_callback=default\n')
        # Retain actual routing, variable loading, tags and connection keywords.
        # NetBox module defaults are irrelevant to routing and their collection
        # is deliberately absent from this no-services fixture.
        for filename in ('netbox_import.yml', 'netbox_import_nexus.yml'):
            plays = yaml.safe_load((SOURCE / filename).read_text())
            for play in plays:
                play.pop('module_defaults', None)
            (self.folder / filename).write_text(yaml.safe_dump(plays, sort_keys=False))
        (self.folder / 'credentials.yml').write_text('netbox_url: https://routing.invalid\nnetbox_token: synthetic-routing-only\n')
        (self.folder / 'vars.json').write_text(json.dumps({'netbox_credentials_file': str(self.folder / 'credentials.yml')}))
        inventory = {'all': {'hosts': {
            'linux-a': {}, 'nexus-var': {'ansible_network_os': 'cisco.nxos.nxos'}},
            'children': {'nexus': {'hosts': {'nexus-group': {}}},
                         'device_roles_nexus-switch': {'hosts': {'nexus-role': {}}}}}}
        (self.folder / 'inventory.yml').write_text(yaml.safe_dump(inventory))
        # Current entrypoint has these five Linux imports; they establish the
        # failing baseline. The merged router has the agreed family boundaries.
        self.probe('tasks/system.yml', 'linux')
        for name in ('components', 'fpga', 'compare', 'apply'):
            (self.folder / f'tasks/{name}.yml').write_text('[]\n')
        self.probe('tasks/import_linux.yml', 'linux')
        self.probe('tasks/import_nexus.yml', 'nexus')
        (self.folder / 'action_plugins/routing_probe.py').write_text('''from ansible.plugins.action import ActionBase
class ActionModule(ActionBase):
    _supports_check_mode = True
    _requires_connection = False
    def run(self, tmp=None, task_vars=None):
        v = task_vars or {}
        message = 'FHS_ROUTING|%s|%s|%s|%s|%s' % (
            self._task.args['family'], v['inventory_hostname'],
            self._task.connection, v.get('netbox_url'), v.get('netbox_api_retries'))
        return dict(changed=False, msg=message, _ansible_verbose_always=True)
''')
        (self.folder / 'action_plugins/fhs_topology_sync.py').write_text(
            'from ansible.plugins.action import ActionBase\nclass ActionModule(ActionBase):\n    def run(self, tmp=None, task_vars=None):\n        return dict(changed=False, plan=[], omissions=[])\n')
        # Transport loading remains part of Ansible scheduling. Its real network
        # handshake is outside a routing unit test; substitute only that driver.
        plugins = self.folder / 'collections/ansible_collections/ansible/netcommon/plugins/connection'
        plugins.mkdir(parents=True)
        (plugins / 'network_cli.py').write_text('from ansible.plugins.connection.local import Connection as Base\nclass Connection(Base):\n    transport = "ansible.netcommon.network_cli"\n')
        self.env = dict(os.environ, ANSIBLE_CONFIG=str(self.folder / 'ansible.cfg'),
                        ANSIBLE_HOME=str(self.folder / 'home'), ANSIBLE_LOCAL_TEMP=str(self.folder / 'tmp'),
                        ANSIBLE_COLLECTIONS_PATH=str(self.folder / 'collections'),
                        ANSIBLE_ACTION_PLUGINS=str(self.folder / 'action_plugins'),
                        ANSIBLE_NOCOLOR='1', ANSIBLE_HOST_KEY_CHECKING='False')

    def probe(self, filename, family):
        (self.folder / filename).write_text(yaml.safe_dump([
            {'name': 'Synthetic routing probe', 'routing_probe': {'family': family}, 'tags': ['always']}
        ]))

    def route(self, *options, entry='netbox_import.yml'):
        command = [*self.command, '-i', str(self.folder / 'inventory.yml'), str(self.folder / entry),
                   '-e', '@' + str(self.folder / 'vars.json'), *options]
        result = subprocess.run(command, cwd=self.folder, env=self.env, text=True,
                                capture_output=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        matches = re.findall(r'FHS_ROUTING\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^"\n]+)', result.stdout)
        self.assertEqual(len(matches), len({row[1] for row in matches}),
                         'A host must execute exactly one device family: ' + repr(matches))
        return {host: (family, connection, url, retries) for family, host, connection, url, retries in matches}

    def assert_routes(self, actual, expected):
        self.assertEqual(set(expected), set(actual), actual)
        for host, family in expected.items():
            self.assertEqual(family, actual[host][0], (host, actual))
            if family == 'nexus':
                self.assertEqual('ansible.netcommon.network_cli', actual[host][1])
            else:
                self.assertNotIn('network_cli', actual[host][1])
            self.assertEqual('https://routing.invalid', actual[host][2], 'Credentials override must reach both paths')
            self.assertEqual('3', actual[host][3], 'Shared API retry default must reach both paths')

    def test_host_failure_does_not_abort_other_hosts_or_next_family(self):
        inventory = yaml.safe_load((self.folder / 'inventory.yml').read_text())
        inventory['all']['hosts']['linux-b'] = {}
        (self.folder / 'inventory.yml').write_text(yaml.safe_dump(inventory))
        tasks = [dict(name='Missing required hardware on one host',
                      **{'ansible.builtin.fail': {'msg': 'Synthetic missing identity'},
                         'when': 'inventory_hostname == "linux-a"', 'tags': ['always']})]
        tasks += yaml.safe_load((self.folder / 'tasks/import_linux.yml').read_text())
        (self.folder / 'tasks/import_linux.yml').write_text(yaml.safe_dump(tasks))
        result = subprocess.run([*self.command, '-i', str(self.folder / 'inventory.yml'),
            str(self.folder / 'netbox_import.yml'), '-e', '@' + str(self.folder / 'vars.json')],
            cwd=self.folder, env=self.env, text=True, capture_output=True, timeout=30)
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn('FHS_ROUTING|linux|linux-b|', result.stdout)
        self.assertIn('FHS_ROUTING|nexus|nexus-var|', result.stdout)
        self.assertNotIn('FHS_ROUTING|linux|linux-a|', result.stdout)

    def test_shared_credentials_default_reaches_both_families(self):
        defaults = yaml.safe_load((self.folder / 'defaults.yml').read_text())
        defaults['netbox_credentials_file'] = str(self.folder / 'credentials.yml')
        (self.folder / 'defaults.yml').write_text(yaml.safe_dump(defaults))
        (self.folder / 'vars.json').write_text('{}')
        self.assert_routes(self.route('--limit', 'linux-a,nexus-var'),
                           {'linux-a': 'linux', 'nexus-var': 'nexus'})

    def test_mixed_inventory_routes_each_family(self):
        self.assert_routes(self.route(), {'linux-a': 'linux', 'nexus-group': 'nexus',
                                         'nexus-var': 'nexus', 'nexus-role': 'nexus'})

    def test_limit_selects_linux_without_nexus_discovery(self):
        self.assert_routes(self.route('--limit', 'linux-a'), {'linux-a': 'linux'})

    def test_limit_selects_nexus_by_group_or_network_os(self):
        for host in ('nexus-group', 'nexus-var'):
            with self.subTest(host=host):
                self.assert_routes(self.route('--limit', host), {host: 'nexus'})

    def test_tag_and_check_modes_still_dispatch_correct_family(self):
        for mode in (('--tags', 'facts'), ('--tags', 'compare'), ('--tags', 'apply'), ('--check', '--tags', 'apply')):
            with self.subTest(mode=mode):
                self.assert_routes(self.route('--limit', 'linux-a,nexus-var', *mode),
                                   {'linux-a': 'linux', 'nexus-var': 'nexus'})

    def test_legacy_entrypoint_delegates_without_duplicate_device_logic(self):
        wrapper = yaml.safe_load((SOURCE / 'netbox_import_nexus.yml').read_text())
        self.assertEqual(1, len(wrapper))
        imported = wrapper[0].get('import_playbook', wrapper[0].get('ansible.builtin.import_playbook'))
        self.assertIsNotNone(imported, 'Compatibility entrypoint must delegate to the shared public implementation')
        self.assertEqual('netbox_import.yml', imported)
        self.assert_routes(self.route('--limit', 'nexus-group', entry='netbox_import_nexus.yml'),
                           {'nexus-group': 'nexus'})


if __name__ == '__main__':
    unittest.main()
