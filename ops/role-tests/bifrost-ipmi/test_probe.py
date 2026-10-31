"""Run the real Ansible module with a synthetic executable, never a physical BMC."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
MODULE=ROOT/'playbooks/netbox/library/fhs_ipmi_probe.py'


class ProbeTest(unittest.TestCase):
    def probe(self, command='fru', timeout=3, pause=False):
        with tempfile.TemporaryDirectory(prefix='fhs-ipmi-probe-') as folder:
            root=Path(folder);capture=root/'argv.json';binary=root/'ipmitool'
            binary.write_text('#!'+sys.executable+'\nimport os,sys,json,time\nfrom pathlib import Path\n'+
                'Path('+repr(str(capture))+').write_text(json.dumps(sys.argv[1:]))\n'+
                ('time.sleep(10)\n' if pause else '')+
                "assert os.environ['IPMI_PASSWORD']==os.environ['IPMITOOL_PASSWORD']=='synthetic-only'\nprint('FRU fixture')\n")
            binary.chmod(0o700)
            params=dict(address='192.0.2.1',username='fixture',password='synthetic-only',binary=str(binary),command=command,timeout=timeout)
            result=subprocess.run([sys.executable,str(MODULE)],input=json.dumps({'ANSIBLE_MODULE_ARGS':params}),capture_output=True,text=True,timeout=8)
            self.assertNotIn('synthetic-only',result.stdout+result.stderr)
            return json.loads(result.stdout),json.loads(capture.read_text()) if capture.exists() else None

    def test_read_only_commands_and_password_environment(self):
        for command,suffix in [('fru',['fru']),('mc_info',['mc','info']),('lan_print',['lan','print','1'])]:
            with self.subTest(command=command):
                result,argv=self.probe(command)
                self.assertFalse(result['changed']);self.assertEqual(0,result['rc'])
                self.assertEqual(suffix,argv[-len(suffix):]);self.assertIn('-E',argv);self.assertNotIn('-P',argv)

    def test_timeout_is_bounded_and_non_destructive(self):
        result,_=self.probe(timeout=1,pause=True)
        self.assertEqual(124,result['rc']);self.assertFalse(result['changed'])

    def test_unsupported_command_does_not_execute(self):
        result,argv=self.probe(command='unsupported')
        self.assertTrue(result['failed']);self.assertIsNone(argv)


if __name__=='__main__':unittest.main()
