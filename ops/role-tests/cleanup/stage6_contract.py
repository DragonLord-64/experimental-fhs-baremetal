"""Focused rendered proxy and offline selection checks; never run runtime roles."""
from pathlib import Path
import os
import subprocess
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[3]
objects = [o for o in yaml.safe_load_all(Path('/tmp/fhs-stage6-render.yaml').read_text()) if o]

def obj(kind, suffix):
    return next(o for o in objects if o['kind'] == kind and o['metadata']['name'] == 'mid-cbf-hw-' + suffix)

for suffix, port in [('devpi', 3141), ('git-proxy', 3128), ('apt-cacher', 3142)]:
    svc = obj('Service', suffix)
    assert svc['spec']['type'] == 'ClusterIP'
    assert svc['spec']['ports'][0]['port'] == port
    deployment = obj('Deployment', suffix)['spec']
    assert deployment['replicas'] == 1
    pod = deployment['template']['spec']
    assert pod['automountServiceAccountToken'] is False
    assert '@sha256:' in pod['containers'][0]['image']
for suffix in ['devpi', 'apt-cacher']:
    assert obj('PersistentVolumeClaim', suffix)['metadata']['annotations']['helm.sh/resource-policy'] == 'keep'
    assert obj('Deployment', suffix)['spec']['strategy']['type'] == 'Recreate'
for suffix in ['devpi', 'git-proxy']:
    assert obj('Deployment', suffix)['spec']['template']['spec']['securityContext']['runAsNonRoot'] is True
squid = obj('ConfigMap', 'git-proxy')['data']['squid.conf']
assert squid.index('http_access deny CONNECT !SSL_ports') < squid.index('http_access allow CONNECT git_domains')
assert squid.rstrip().endswith('http_access deny all')
assert 'ssl_bump' not in squid and 'cache deny all' in squid
assert 'gitlab.com git-collab.nrc-cnrc.gc.ca' in squid
script = obj('ConfigMap', 'devpi')['data']['start.sh']
assert '/var/devpi/.serverversion' in script and '--restrict-modify root' in script
site = yaml.safe_load((ROOT / 'playbooks/site.yml').read_text())
for play in site:
    for task in play.get('tasks', []):
        if 'ansible.builtin.include_role' in task:
            role = task['ansible.builtin.include_role']['name']
            assert role in task['tags'] and role in task['ansible.builtin.include_role']['apply']['tags']
assert site[-1]['tags'] == ['rsync']
assert not any('rsync' in p.read_text() for p in (ROOT / 'roles/setup_fpga_host/tasks').glob('*.yml'))
for role in ['manage_users', 'manage_bittware_sdk', 'setup_apt_source', 'setup_pip_source', 'setup_git_proxy']:
    assert not any('tags: [' in p.read_text() for p in (ROOT / 'roles' / role / 'tasks').glob('*.yml'))

# Ansible executes the actual main.yml import/when/tag logic with inert imported
# actions. Never invoke any real udev, GRUB, firmware, SDK or service task.
with tempfile.TemporaryDirectory(prefix='fhs-stage6-tags-') as tmp:
    dest = Path(tmp)
    role = dest / 'roles/setup_fpga_host'
    (role / 'tasks').mkdir(parents=True)
    (role / 'defaults').mkdir()
    (role / 'defaults/main.yml').write_text((ROOT / 'roles/setup_fpga_host/defaults/main.yml').read_text())
    (role / 'tasks/main.yml').write_text((ROOT / 'roles/setup_fpga_host/tasks/main.yml').read_text())
    for name in ['udev', 'grub', 'bmc_firmware']:
        (role / f'tasks/{name}.yml').write_text(yaml.safe_dump([{'name': 'SAFE_' + name, 'ansible.builtin.debug': {'msg': 'SAFE_' + name}}]))
    play = [{'hosts': 'all', 'gather_facts': False, 'tasks': [{'name': 'Site FPGA selection', 'ansible.builtin.include_role': {'name': 'setup_fpga_host', 'apply': {'tags': ['setup_fpga_host']}}, 'tags': ['setup_fpga_host']}]}]
    (dest / 'test.yml').write_text(yaml.safe_dump(play))
    env = dict(os.environ, ANSIBLE_ROLES_PATH=str(dest / 'roles'), ANSIBLE_LOCAL_TEMP=str(dest / 'local'), ANSIBLE_NOCOLOR='1')
    for tags, flag, expected in [(None, True, False), ('setup_fpga_host', True, False), ('setup_fpga_host,firmware', False, False), ('setup_fpga_host,firmware', True, True)]:
        cmd = ['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(dest / 'test.yml'), '-e', 'fpga_update_bmc=' + str(flag).lower()]
        if tags:
            cmd += ['--tags', tags]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert ('"msg": "SAFE_bmc_firmware"' in result.stdout) == expected, (tags, flag, result.stdout)
        assert '"msg": "SAFE_udev"' in result.stdout
        assert '"msg": "SAFE_grub"' not in result.stdout
        print(f'Inert actual-main selection: tags={tags}, firmware flag={flag}, execution={expected}')
print('Rendered proxy services/PVC/security and site tag/firmware selection passed.')
