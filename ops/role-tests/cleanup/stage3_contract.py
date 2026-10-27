"""Finite stage-3 source/selection and sanitized effective-policy checks; no apply."""
from pathlib import Path
import tempfile
import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager
from ansible.vars.manager import VariableManager
from ansible.template import Templar, trust_as_template

ROOT = Path(__file__).resolve().parents[3]
def load(p):
    return yaml.safe_load((ROOT / p).read_text())

def walk(tasks):
    for task in tasks:
        yield task
        for key in ('block', 'rescue', 'always'):
            yield from walk(task.get(key, []))

# Service ownership and explicit-only file deletion, not a second Ansible engine.
network = load('roles/setup_fhs_network/tasks/main.yml')
config = load('roles/setup_fhs_network/tasks/configure.yml')
assert network[0]['ansible.builtin.import_tasks'] == 'validate.yml'
assert not any('ansible.builtin.find' in t for t in walk(config))
deletes = [t for t in walk(config) if t.get('ansible.builtin.file', {}).get('state') == 'absent']
assert len(deletes) == 2
assert deletes[0]['ansible.builtin.file']['path'] == '{{ network_dir }}/99-ignore-others.network'
assert deletes[1]['when'] == 'network_remove_legacy_netplan | bool'
assert 'cloud-init.disabled' not in str(config)
service = next(t for t in network if 'ansible.builtin.systemd_service' in t)
assert service['loop'] == ['systemd-networkd', 'systemd-resolved', 'systemd-timesyncd']
assert service['ansible.builtin.systemd_service']['enabled'] is True
assert service['ansible.builtin.systemd_service']['state'] == 'started'
assert next(t for t in network if t['name'] == 'Use resolved stub resolver')['ansible.builtin.file']['src'] == '/run/systemd/resolve/stub-resolv.conf'
node_tasks = []
for path in (ROOT / 'roles/setup_fhs_node/tasks').glob('*.yml'):
    node_tasks += list(walk(yaml.safe_load(path.read_text())))
assert not any(t.get('ignore_errors') for t in node_tasks)
assert not any('ansible.builtin.reboot' in t for t in node_tasks)
assert not any('kubeadm join' in str(t.get('ansible.builtin.command', '')) + str(t.get('ansible.builtin.shell', '')) for t in node_tasks)
node = load('roles/setup_fhs_node/tasks/main.yml')
cleanup = next(t for t in node if t['name'] == 'Cleanup previous Kubernetes installation')
assert cleanup['tags'] == ['cleanup', 'never'] and cleanup['when'] == "'cleanup' in ansible_run_tags"
assert load('roles/setup_fhs_node/defaults/main.yml')['k8s_enable_ceph'] is False

site = load('playbooks/site.yml')
cis = next(p for p in site if p['name'] == 'Ubuntu 24 Linux server policy')
assert cis['hosts'] == 'ubuntu24_cis_production'
assert cis['tasks'][0]['ansible.builtin.import_tasks'] == 'tasks/cis-policy-preflight.yml'
assert not any(t.get('vars', {}).get('audit_only') for t in cis['tasks'])

# Parse only the public classification expression, never emit private inventory.
line = next(l for l in (ROOT / 'inventory/dev_env/netbox-inv.yml').read_text().splitlines() if l.startswith('  ubuntu24_cis_production:'))
expr = yaml.safe_load(line)['ubuntu24_cis_production']
loader = DataLoader()
for variables, expected in [
    ({'tags': [], 'device_role': {'slug': 'fpga-host-server'}}, True),
    ({'tags': [{'slug': 'fpga-host-server'}], 'device_role': {'slug': 'other'}}, True),
    ({'tags': [], 'device_role': {'slug': 'control'}, 'config_context': {'fhs_linux_server': True}}, True),
    ({'tags': [{'slug': 'nexus-switch'}], 'device_role': {'slug': 'nexus-switch'}}, False),
]:
    assert bool(Templar(loader=loader, variables=variables).template(trust_as_template('{{ ' + expr + ' }}'))) == expected

# Actual inventory manager inheritance: policy reaches non-node Linux too.
with tempfile.TemporaryDirectory(prefix='fhs-stage3-inventory-') as tmp:
    dest = Path(tmp)
    (dest / 'group_vars').mkdir()
    (dest / 'group_vars/ubuntu24_cis_production.yml').write_text((ROOT / 'inventory/dev_env/group_vars/ubuntu24_cis_production.yml').read_text())
    (dest / 'hosts.yml').write_text((ROOT / 'inventory/dev_env/hosts.yml').read_text())
    (dest / 'fixture.yml').write_text(yaml.safe_dump({
        'device_roles_fpga-host-server': {'hosts': {'fixture-compute': {}}},
        'fhs_nodes': {'hosts': {'fixture-node': {}}},
        'control_servers': {'hosts': {'fixture-control': {}}},
        'nexus': {'hosts': {'fixture-switch': {}}},
    }))
    inv = InventoryManager(loader=loader, sources=[str(dest)])
    vm = VariableManager(loader=loader, inventory=inv)
    for name in ('fixture-compute', 'fixture-node', 'fixture-control'):
        effective = vm.get_vars(host=inv.get_host(name))
        assert 'ubuntu24_cis_production' in effective['group_names']
        for key in ('audit_only', 'ubtu24cis_section4', 'ubtu24cis_rule_5_2_4', 'ubtu24cis_rule_1_2_2_1', 'ubtu24cis_rule_6_3_1', 'ubtu24cis_rule_5_3_1_3'):
            assert effective[key] is False, (name, key)
        assert effective['skip_reboot'] is True
        assert effective['ubtu24cis_time_sync_tool'] == 'systemd-timesyncd'
        assert effective['ubtu24cis_auditd_admin_space_left_action'] == 'syslog'
        variables = dict(effective, ansible_facts={'system': 'Linux', 'distribution': 'Ubuntu', 'distribution_version': '24.04'})
        templar = Templar(loader=loader, variables=variables)
        for condition in load('playbooks/tasks/cis-policy-preflight.yml')[0]['ansible.builtin.assert']['that']:
            assert templar.template(trust_as_template('{{ ' + condition + ' }}')) is True, (name, condition)
    assert 'ubuntu24_cis_production' not in vm.get_vars(host=inv.get_host('fixture-switch'))['group_names']
print('Stage 3 source safety, NetBox classification and three-host effective CIS policy passed; switch excluded.')
