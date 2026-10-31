"""Exercise real delegated tasks with SSH inventory and no reachable SSH target."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[3]


class DelegationTest(unittest.TestCase):
    def test_ipmi_runs_locally_despite_ssh_inventory(self):
        with tempfile.TemporaryDirectory(prefix='fhs-ipmi-delegation-') as folder:
            root = Path(folder)
            binary = root / 'ipmitool'
            binary.write_text('#!' + sys.executable + '\nimport sys\n'
                "if sys.argv[-1:] == ['fru']: print('FRU Device Description : Builtin FRU Device (ID 0)\\n Product Serial : SYN-DELEGATION')\n"
                "elif sys.argv[-2:] == ['mc','info']: print('Firmware Revision : 1.23')\n"
                "else: print('IP Address : 192.0.2.20')\n")
            binary.chmod(0o700)
            inventory = root / 'inventory.yml'
            inventory.write_text(yaml.safe_dump({'all': {'hosts': {
                'localhost': {'ansible_connection': 'ssh', 'ansible_host': '192.0.2.254'},
                'fixture': {'ansible_connection': 'ssh', 'ansible_host': '192.0.2.253'}}}}))
            play = [{'hosts': 'fixture', 'gather_facts': False, 'vars': {
                'netbox_ipmi_address': '192.0.2.20', 'netbox_ipmi_username': 'fixture',
                'netbox_ipmi_password': 'synthetic-only', 'netbox_ipmi_binary': str(binary),
                'hardware_command_path': os.environ['PATH'], 'hardware_fields': {},
                'discovered_components': [], 'server_info': {}, 'unavailable_values': ['', 'unknown']},
                'tasks': [
                    {'ansible.builtin.include_tasks': str(ROOT/'playbooks/netbox/tasks/identity.yml')},
                    {'ansible.builtin.include_tasks': str(ROOT/'playbooks/netbox/tasks/bmc_metadata.yml')},
                    {'ansible.builtin.assert': {'that': [
                        "system_identity.identity.serial == 'SYN-DELEGATION'",
                        "bmc_info_probe.rc == 0", "bmc_lan_probe.rc == 0",
                        "bmc_address == '192.0.2.20'"]}}]}]
            source = root / 'play.yml'; source.write_text(yaml.safe_dump(play))
            env = dict(os.environ, ANSIBLE_LOCAL_TEMP=str(root/'tmp'), ANSIBLE_REMOTE_TEMP=str(root/'remote-tmp'),
                ANSIBLE_FILTER_PLUGINS=str(ROOT/'playbooks/netbox/filter_plugins'),
                ANSIBLE_LIBRARY=str(ROOT/'playbooks/netbox/library'))
            executable = str(Path(sys.executable).parent/'ansible-playbook')
            result = subprocess.run([executable, '-i', str(inventory), str(source)],
                env=env, capture_output=True, text=True, timeout=45)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
