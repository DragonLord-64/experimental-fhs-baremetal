#!/usr/bin/python
"""Bounded, read-only network IPMI probes; passwords never appear in argv."""
import os
import subprocess
from ansible.module_utils.basic import AnsibleModule


def main():
    module = AnsibleModule(argument_spec=dict(
        address=dict(required=True), username=dict(required=True),
        password=dict(required=True, no_log=True), port=dict(type='int', default=623),
        command=dict(choices=['fru', 'mc_info', 'lan_print'], default='fru'),
        channel=dict(type='int', default=1), timeout=dict(type='int', default=45),
        binary=dict(type='path', default='ipmitool')), supports_check_mode=True)
    p = module.params
    if not p['address'] or not p['username'] or not p['password'] or not 1 <= p['port'] <= 65535 or not 1 <= p['timeout'] <= 300 or not 0 <= p['channel'] <= 15:
        module.fail_json(msg='Supply a BMC address, credentials and valid IPMI port/channel/timeout')
    binary = p['binary'] if '/' in p['binary'] else module.get_bin_path(p['binary'], required=True)
    argv = [binary, '-I', 'lanplus', '-H', p['address'], '-p', str(p['port']),
            '-U', p['username'], '-E', '-N', '5', '-R', '1']
    argv += {'fru':['fru'], 'mc_info':['mc','info'], 'lan_print':['lan','print',str(p['channel'])]}[p['command']]
    env = dict(os.environ, IPMI_PASSWORD=p['password'], IPMITOOL_PASSWORD=p['password'], LC_ALL='C', LANG='C')
    try:
        result = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=p['timeout'])
        module.exit_json(changed=False, rc=result.returncode, stdout=result.stdout,
                         stderr='' if result.returncode == 0 else 'Remote IPMI read failed; check BMC access and credentials')
    except subprocess.TimeoutExpired:
        module.exit_json(changed=False, rc=124, stdout='', stderr='Remote IPMI read timed out')
    except OSError:
        module.fail_json(msg='Cannot execute controller ipmitool; install it on the probe delegate')


if __name__ == '__main__':
    main()
