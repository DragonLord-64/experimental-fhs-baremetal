#!/usr/bin/python
"""Read installed SDK entrypoints as the configured tooling user; never install."""
import os
from pathlib import Path
import pwd
import re
from ansible.module_utils.basic import AnsibleModule


def main():
    module = AnsibleModule(argument_spec=dict(venv=dict(required=True, type='path'),
        sdk_root=dict(required=True, type='path'), user=dict(required=True),
        card_argv=dict(type='list', elements='str', required=True),
        qsfp_argv=dict(type='list', elements='str', required=True),
        command_path=dict(required=True)), supports_check_mode=True)
    p = module.params; diagnostics = []
    def finish(reason, rc=1):
        module.exit_json(changed=False, failed=False, rc=rc, stdout='', cards={}, qsfp=[], diagnostics=diagnostics, omission=reason)
    card_args = p['card_argv']; qsfp_args = p['qsfp_argv']
    if (not card_args or Path(card_args[0]).name != 'bw_card_list' or card_args[1:] not in (['-v', '-i', 'USB'], ['-i', 'USB', '-v']) or
        len(qsfp_args) != 1 or Path(qsfp_args[0]).name != 'bw_qsfp_info'):
        finish('SDK discovery permits only the configured read-only bw_card_list USB and bw_qsfp_info display commands')
    actual_user = pwd.getpwuid(os.geteuid()).pw_name
    if actual_user != p['user']: finish('SDK user mismatch; configure become_user for the BittWare account')
    python = Path(p['venv']) / 'bin/python3'
    if not python.is_file() or not os.access(python, os.X_OK): finish('SDK venv Python missing or not executable; provision the configured venv')
    if not Path(p['sdk_root']).is_dir(): finish('BWSDK_ROOT is missing; provision the SDK with manage_bittware_sdk')
    environment = dict(os.environ, BWSDK_ROOT=p['sdk_root'], PATH=str(Path(p['venv'])/'bin')+':'+p['command_path'], LC_ALL='C')
    def executable(argv):
        tool = Path(argv[0]) if '/' in argv[0] else Path(p['venv']) / 'bin' / argv[0]
        if not tool.is_file() or not os.access(tool, os.R_OK | os.X_OK):
            finish('Installed SDK entrypoint unavailable: ' + tool.name + '; provisioning owns SDK installation')
        return [str(python), str(tool)] + argv[1:]
    card_command = executable(p['card_argv']); qsfp_command = executable(p['qsfp_argv'])
    # --help imports each entrypoint's real Python dependencies without probing or
    # modifying hardware. It avoids guessing the SDK's private package names.
    for label, command in (('bw_card_list', card_command), ('bw_qsfp_info', qsfp_command)):
        rc, out, err = module.run_command(command[:2]+['--help'], environ_update=environment)
        diagnostics.append(dict(probe=label+' Python dependency check', rc=rc, user=actual_user,
                                venv=p['venv'], sdk_root=p['sdk_root']))
        if rc: finish(label + ': installed entrypoint/Python dependency check failed; repair provisioning')
    rc, out, err = module.run_command(card_command, environ_update=environment)
    diagnostics.append(dict(probe='USB card list', rc=rc, user=actual_user))
    if rc:
        reason = 'USB card list failed'
        if 'permission' in (out+err).lower() or 'access denied' in (out+err).lower():
            reason += '; check BittWare group and USB device permissions for configured user'
        else: reason += '; SDK cannot enumerate USB cards (inspect private capture)'
        module.exit_json(changed=False, failed=False, rc=rc, stdout=out, stderr=err, qsfp=[], diagnostics=diagnostics, omission=reason)
    indices = list(dict.fromkeys(int(i) for i in re.findall(r'^\s*Index\s*:\s*(\d+)\b', out, re.M)))
    probes = []
    for index in indices:
        qrc, qout, qerr = module.run_command(qsfp_command+['-c', str(index), '-i', 'USB', 'display'], environ_update=environment)
        probes.append(dict(rc=qrc, stdout=qout, stderr=qerr, item=dict(card_index=index)))
        diagnostics.append(dict(probe='USB QSFP display', card_index=index, rc=qrc, user=actual_user))
    module.exit_json(changed=False, rc=0, stdout=out, stderr=err, qsfp=probes, diagnostics=diagnostics, omission='')


if __name__ == '__main__': main()
