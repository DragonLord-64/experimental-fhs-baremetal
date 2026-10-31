"""Private files and bounded native application execution."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]


class Error(Exception):
    pass


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(argv, *, timeout=180, env=None, data=None):
    # Ansible progress is live; other application output is exposed with -v.
    visible = str(argv[0]).startswith("ansible") or bool(os.environ.get("HWMANAGE_VERBOSE"))
    if str(argv[0]).startswith('ansible'):
        env = dict(os.environ if env is None else env, ANSIBLE_LOG_PATH='/dev/null',
                   ANSIBLE_CACHE_PLUGIN='memory')
    if str(argv[0]).startswith('ansible-playbook') and os.environ.get('HWMANAGE_VERBOSE'):
        argv = [*argv, '-'+('v'*min(int(os.environ['HWMANAGE_VERBOSE']), 4))]
    fd, diagnostic = tempfile.mkstemp(prefix='hwmanage-diagnostic-', suffix='.log')
    os.fchmod(fd, 0o600)
    try:
        if visible:
            print('Running: '+str(argv[0]), flush=True)
            output = []
            errors = []
            with subprocess.Popen([str(v) for v in argv], stdin=subprocess.PIPE if data is not None else None,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env) as process:
                def relay(stream, captured, destination):
                    for line in stream:
                        captured.append(line)
                        print(line, end='', file=destination, flush=True)
                reader = threading.Thread(target=relay, args=(process.stdout, output, sys.stdout))
                error_reader = threading.Thread(target=relay, args=(process.stderr, errors, sys.stderr))
                reader.start()
                error_reader.start()
                try:
                    if data is not None:
                        process.stdin.write(data)
                        process.stdin.close()
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    reader.join()
                    error_reader.join()
                    raise subprocess.TimeoutExpired(argv, timeout, output=''.join(output), stderr=''.join(errors)) from None
                reader.join()
                error_reader.join()
                result = subprocess.CompletedProcess(argv, process.returncode, ''.join(output), ''.join(errors))
        else:
            result = subprocess.run([str(v) for v in argv], input=data, capture_output=True,
                                    text=True, timeout=timeout, env=env)
    except FileNotFoundError:
        os.close(fd)
        os.unlink(diagnostic)
        raise Error('Required application unavailable: '+str(argv[0])) from None
    except subprocess.TimeoutExpired as error:
        with os.fdopen(fd, 'w') as stream:
            for output in (error.stdout, error.stderr):
                stream.write(output.decode(errors='replace') if isinstance(output, bytes) else output or '')
        raise Error(str(argv[0])+' timed out; private diagnostics: '+diagnostic+'; inspect state before retry') from None
    with os.fdopen(fd, 'w') as stream:
        stream.write(result.stdout or '')
        stream.write(result.stderr or '')
    if result.returncode:
        if not visible:
            print(result.stdout or '', end='', flush=True)
            print(result.stderr or '', end='', file=sys.stderr, flush=True)
        raise Error(str(argv[0])+' failed (exit '+str(result.returncode)+'); private diagnostics: '+diagnostic)
    if str(argv[0]).startswith('ansible-playbook'):
        print('ansible-playbook completed (exit 0); private diagnostics: '+diagnostic, flush=True)
    else:
        os.unlink(diagnostic)
    return result.stdout


def yaml_load(path):
    try:
        import yaml
    except ImportError:
        raise Error('This command requires PyYAML') from None
    with open(path) as stream:
        return yaml.safe_load(stream)


def private_write(path, value):
    # Never overwrite an existing path or follow a symlink.
    import yaml
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        yaml.safe_dump(value, stream, sort_keys=False)


def temp_json(directory, name, value):
    path = Path(directory) / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream)
    return str(path)


def workspace():
    return tempfile.TemporaryDirectory(prefix='hwmanage-')


def safe_name(value):
    import re
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value):
        raise Error('A real, unambiguous hostname is required')
    return value


def is_nexus(host):
    return (host.get('ansible_network_os') in ('nxos', 'cisco.nxos.nxos') or
            any(g in ('nexus', 'device_roles_nexus-switch', 'device_roles_nexus_switch')
                for g in host.get('host_groups', [])))


def protected_yaml(path):
    """Use Ansible's configured Vault identities/password file when encrypted."""
    raw = Path(path).read_bytes()
    if not (raw.startswith(b'$ANSIBLE_VAULT') or b'!vault' in raw):
        return yaml_load(path)
    try:
        from ansible import constants as C
        from ansible.cli import CLI
        from ansible.parsing.dataloader import DataLoader
        loader = DataLoader()
        passwords = [C.DEFAULT_VAULT_PASSWORD_FILE] if C.DEFAULT_VAULT_PASSWORD_FILE else []
        secrets = CLI.setup_vault_secrets(loader, vault_ids=list(C.DEFAULT_VAULT_IDENTITY_LIST or []),
                                          vault_password_files=passwords, auto_prompt=False)
        loader.set_vault_secrets(secrets)
        return loader.load_from_file(str(path))
    except Exception:
        raise Error('Unable to decrypt protected variables using configured Ansible Vault access') from None
