"""Small argparse interface; importing this module needs only Python's stdlib."""
import argparse
import json
import os
import sys
import traceback
from .common import Error

RUNBOOKS = {
    'inspect-host': ('enroll', 'manage', 'inspect'),
    'provide-node': ('enroll', 'manage', 'clean', 'provide', 'deploy', 'waitSSH'),
    'full-provision': ('enroll', 'manage', 'clean', 'provide', 'deploy', 'waitSSH', 'provision', 'inventory'),
}


class Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument('-v', '--verbose', action='count', default=argparse.SUPPRESS,
                          help='Show application output and increase Ansible verbosity (repeat for more detail)')

    def error(self, message):
        # argparse's default errors can echo an unknown argument containing a secret.
        self.print_usage(sys.stderr)
        self.exit(2, 'Invalid or missing arguments; use --help for this command.\n')


def target(parser, default='netbox', required=True):
    parser.add_argument('-i', '--inventory', default=default, help='netbox, ironic, or explicit native YAML inventory')
    group = parser.add_mutually_exclusive_group(required=required)
    group.add_argument('--limit', help='Ansible host pattern, or exact Ironic name/UUID')
    group.add_argument('--all', action='store_true', help='Explicitly select all records')


def individual(parser, ansible=False):
    parser.add_argument('--plan', action='store_true', help='Resolve and validate; do not change applications')
    if ansible:
        parser.add_argument('-e', '--extra-vars', action='append', default=[], help='Native Ansible variables; use @protected-file for secrets')
        parser.add_argument('--tags', help='Native Ansible tags')
        parser.add_argument('--skip-tags', help='Native Ansible skip tags')


def parser():
    root = Parser(description='Explicit Ironic/Bifrost lifecycle and scoped Ansible provisioning. Run inside the provisioning container.')
    groups = root.add_subparsers(dest='group', required=True)
    node = groups.add_parser('node', help='Ironic node database and lifecycle')
    commands = node.add_subparsers(dest='action', required=True)
    for action in ('list', 'show', 'enroll', 'sync', 'manage', 'inspect', 'clean', 'provide', 'deploy', 'adopt'):
        child = commands.add_parser(action, help='Native node '+action)
        target(child, default='ironic' if action == 'list' else 'netbox', required=action != 'list')
        individual(child, ansible=action == 'deploy')
        if action == 'clean':
            child.add_argument('--clean-steps', help='JSON list, JSON file, or - for stdin; default erase_devices_metadata')
    inventory = groups.add_parser('inventory', help='Minimal pre-OS import and portable Bifrost YAML export')
    commands = inventory.add_subparsers(dest='action', required=True)
    for action in ('import', 'export'):
        child = commands.add_parser(action)
        target(child, default='ironic' if action == 'import' else 'netbox')
        individual(child)
        if action == 'export':
            output = child.add_mutually_exclusive_group(required=True)
            output.add_argument('--output', help='New private native Bifrost YAML file')
            output.add_argument('--output-dir', help='New private portable Bifrost/Ansible snapshot directory')
    provision = groups.add_parser('provision', help='Run playbooks/provision.yml; --tags inventory opts into detailed collection')
    target(provision)
    individual(provision, ansible=True)
    run = groups.add_parser('run', help='Fixed sequences; no behavior overrides')
    commands = run.add_subparsers(dest='action', required=True)
    commands.add_parser('list', help='List fixed runbooks')
    for action in RUNBOOKS:
        child = commands.add_parser(action, help=' -> '.join(RUNBOOKS[action]))
        target(child)
    config = groups.add_parser('config', help='Validate explicit configuration edits; no service restarts')
    commands = config.add_subparsers(dest='action', required=True)
    ironic = commands.add_parser('ironic', help='Set effective conductor cleaning policy; report restart needed')
    ironic.add_argument('--automated-clean', choices=['false'], required=True)
    individual(ironic)
    dns = commands.add_parser('dnsmasq', help='Own only the dedicated hwmanage.conf include')
    commands = dns.add_subparsers(dest='dns_action', required=True)
    commands.add_parser('list-hosts')
    for action in ('add-host', 'remove-host'):
        child = commands.add_parser(action)
        target(child)
        individual(child)
        if action == 'add-host':
            for arg in ('mac', 'ip', 'group', 'boot-server', 'boot-file'):
                child.add_argument('--'+arg, *(['--image'] if arg == 'boot-file' else []), dest='group_override' if arg == 'group' else arg.replace('-', '_'))
    check = groups.add_parser('check', help='Read-only native checks')
    commands = check.add_subparsers(dest='action', required=True)
    commands.add_parser('systems')
    child = commands.add_parser('hosts')
    target(child)
    return root


def summary(hosts):
    # Never serialize driver_info, instance_info or arbitrary service payloads.
    for key, host in hosts.items():
        print(json.dumps({field: host.get(field) for field in ('name', 'uuid', 'provision_state', 'maintenance')}))


def node_command(args, hosts):
    from .ironic import Ironic, clean_steps, guard
    if args.action in ('list', 'show'):
        summary(hosts)
        return
    from .common import is_nexus
    if any(is_nexus(h) for h in hosts.values()):
        raise Error('Switches cannot enter the Ironic lifecycle')
    if args.action == 'deploy':
        from .provision import effective_hosts, deployment_preflight
        hosts = effective_hosts(hosts)
        deployment_preflight(hosts, args)
    client = Ironic()
    steps = clean_steps(args.clean_steps) if args.action == 'clean' else None
    failures = 0
    for key, host in hosts.items():
        try:
            if args.action in ('enroll', 'sync'):
                node = client.reconcile(host, create=args.action == 'enroll', plan=args.plan)
            else:
                match = client.api.find_node(host.get('uuid') or host.get('name'))
                if not match:
                    raise Error('Node is not enrolled')
                from .ironic import normalize
                node = normalize(match)
                client.action(node, args.action, host=host, steps=steps, options=args, plan=args.plan)
            print(str(node.get('uuid') or key)+': '+('planned ' if args.plan else 'completed ')+args.action)
        except Exception:
            traceback.print_exc()
            failures += 1
            print(str(host.get('uuid') or key)+': failed '+args.action+'; later stages stopped, inspect protected state/logs', file=sys.stderr)
    if failures:
        raise Error(str(failures)+' node operation(s) failed')


def runbook(args, hosts):
    from .ironic import Ironic, guard, normalize, automatic_clean_disabled, DEFAULT_CLEAN
    from .common import is_nexus
    from .provision import apply, effective_hosts, deployment_preflight
    hosts = effective_hosts(hosts)
    if args.action != 'inspect-host':
        deployment_preflight(hosts)
    client = Ironic()
    # Validate the entire selection before the first enrollment or lifecycle write.
    import copy
    hosts = copy.deepcopy(hosts)
    for host in hosts.values():
        if is_nexus(host):
            raise Error('Lifecycle runbooks cannot select switches')
        node = client.reconcile(host, create=True, plan=True)
        if node.get('uuid'):
            guard(node, 'manage', pipeline=True)
            host['uuid'] = node['uuid']
    failures = 0
    for key, host in hosts.items():
        try:
            node = client.reconcile(host, create=True)
            host = dict(host, uuid=node['uuid'])
            if node['provision_state'] != 'manageable':
                client.action(node, 'manage')
                node = client.get(node['uuid'])
            if args.action == 'inspect-host':
                client.action(node, 'inspect')
            else:
                client.action(node, 'clean', steps=DEFAULT_CLEAN)
                node = client.get(node['uuid'])
                automatic_clean_disabled(node)
                client.action(node, 'provide')
                node = client.get(node['uuid'])
                client.action(node, 'deploy', host=host)
                apply({host['name']: host}, wait=True, wait_only=True)
                if args.action == 'full-provision':
                    apply({host['name']: host})
                    apply({host['name']: host}, inventory_only=True)
            print(node['uuid']+': completed '+args.action)
        except Exception:
            traceback.print_exc()
            failures += 1
            print(str(host.get('uuid') or key)+': failed runbook; later stages stopped, inspect before retry', file=sys.stderr)
    if failures:
        raise Error(str(failures)+' runbook target(s) failed')


def dispatch(args):
    if args.group == 'run' and args.action == 'list':
        for name, stages in RUNBOOKS.items():
            print(name+': '+' -> '.join(stages))
        return
    if args.group == 'check' and args.action == 'systems':
        from .checks import systems
        return systems()
    if args.group == 'config' and args.action == 'ironic':
        from .config import set_ironic
        return set_ironic(args.plan)
    if args.group == 'config' and args.dns_action == 'list-hosts':
        from .config import dnsmasq
        return dnsmasq('list-hosts')
    from .inventory import resolve
    hosts = resolve(args.inventory, args.limit)
    if args.group == 'node':
        return node_command(args, hosts)
    if args.group == 'provision':
        from .provision import apply
        return apply(hosts, args, plan=args.plan)
    if args.group == 'run':
        return runbook(args, hosts)
    if args.group == 'check':
        from .checks import hosts as check_hosts
        return check_hosts(hosts)
    if args.group == 'config':
        from .config import dnsmasq
        # Preserve the top-level command discriminator.
        from types import SimpleNamespace
        options = SimpleNamespace(**vars(args))
        options.group = getattr(args, 'group_override', None)
        for key in ('mac', 'ip', 'boot_server', 'boot_file'):
            if not hasattr(options, key):
                setattr(options, key, None)
        return dnsmasq(args.dns_action, hosts, options)
    if args.action == 'export':
        from .inventory import export
        if not args.plan:
            export(hosts, args.output, output_dir=args.output_dir)
        print(str(len(hosts))+' host(s) '+('validated for export' if args.plan else 'exported privately'))
    else:
        if args.inventory != 'ironic':
            raise Error('Minimal pre-OS import requires -i ironic; YAML remains available for enrollment, export and provisioning')
        from .common import ROOT, run, workspace, temp_json
        with workspace() as directory:
            selected = temp_json(directory, 'selected.json', {'hwmanage_selected_uuids': [h['uuid'] for h in hosts.values()]})
            run(['ansible-playbook', '-i', 'localhost,', ROOT/'playbooks/netbox/ironic_import.yml',
                 '-e', '@'+selected, *(['--check'] if args.plan else [])],
                timeout=int(os.environ.get('HWMANAGE_ANSIBLE_TIMEOUT', '7200')))
        print(str(len(hosts))+' minimal device(s) '+('planned' if args.plan else 'imported'))


def main(argv=None):
    args = parser().parse_args(argv)
    verbosity = getattr(args, 'verbose', 0)
    if verbosity:
        os.environ['HWMANAGE_VERBOSE'] = str(verbosity)
    try:
        dispatch(args)
        return 0
    except Error as error:
        print('hwmanage: '+str(error), file=sys.stderr)
    except Exception:
        traceback.print_exc()
    return 1
