"""Read-only checks; failed checks never repair a service."""
import os
from urllib.parse import urlsplit
from urllib.request import urlopen
from .common import Error, ROOT, run, temp_json, workspace


def systems():
    from .config import ironic_policy
    from .inventory import netbox_api
    failed = []
    checks = {
        'Ironic API/drivers': lambda: run(['baremetal', 'driver', 'list', '-f', 'json']),
        'Ironic automatic cleaning disabled': lambda: ironic_policy() is False,
        'Ironic native checks': lambda: run(['ironic-status', 'upgrade', 'check']),
        'dnsmasq syntax': lambda: run(['dnsmasq', '--test', '--conf-file='+os.environ.get('HWMANAGE_DNSMASQ_CONFIG', '/etc/dnsmasq.conf')]),
        'NetBox API': lambda: netbox_api().request('GET', 'status/'),
        'boot HTTP': boot_http,
        'Ansible provisioning syntax': ansible_syntax,
    }
    services = os.environ.get('HWMANAGE_SERVICES', 'ironic-api ironic-conductor dnsmasq').split()
    checks.update({name+' service': lambda n=name: run(['systemctl', 'is-active', n]) for name in services})
    checks.update({name+' recent errors': lambda n=name: recent_errors(n) for name in services})
    for label, check in checks.items():
        try:
            if check() is False:
                raise Error('Policy is not disabled')
            print(label+': OK')
        except Exception as error:
            print(label+': FAILED (inspect configuration/access privately)')
            if isinstance(error, Error):
                print(str(error))
            failed.append(label)
    if failed:
        raise Error(str(len(failed))+' system checks failed')


def boot_http():
    url = os.environ.get('HWMANAGE_BOOT_URL')
    if not url:
        raise Error('Set checks.boot_url in hwmanage config.yml to an actual boot asset URL')
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
        raise Error('Boot URL must be HTTP(S) without credentials')
    with urlopen(url, timeout=15) as response:
        if response.status != 200 or not response.read(1):
            raise Error('Boot asset unavailable')
    return True


def hosts(hosts):
    from .inventory import as_inventory
    from .provision import site_vars_source
    with workspace() as directory:
        source = temp_json(directory, 'inventory.json', as_inventory(hosts))
        run(['ansible-playbook', '-i', site_vars_source(), '-i', source, ROOT/'playbooks/hwmanage_check_hosts.yml',
             '--limit', ','.join(hosts)])
    print(str(len(hosts))+' host connectivity checks passed')


def ansible_syntax():
    from .provision import site_vars_source
    run(['ansible-playbook', '-i', site_vars_source(), ROOT/'playbooks/provision.yml', '--syntax-check'])
    return True


def recent_errors(service):
    # Read a bounded recent window; never print journal payloads, which may be sensitive.
    output = run(['journalctl', '--unit', service, '--since', '-15min',
                  '--priority', 'err', '--lines', '20', '--no-pager', '--quiet'])
    if output.strip():
        raise Error('Recent service errors found; inspect the service journal privately')
    return True
