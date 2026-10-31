"""Edit only explicit configuration files; never restart services."""
import configparser
import ipaddress
import os
from pathlib import Path
import re
import tempfile
from .common import Error, is_nexus, run, safe_name, workspace

HEADER = '# Managed by hwmanage; dedicated include only.\n'


def ironic_files():
    return [Path(p) for p in os.environ.get('HWMANAGE_IRONIC_CONFIG', '/etc/ironic/ironic.conf').split(os.pathsep)]


def ironic_policy(paths=None):
    paths = paths or ironic_files()
    parser = configparser.ConfigParser(interpolation=None)
    for path in paths:
        if not path.is_file():
            raise Error('Effective Ironic config unavailable; set HWMANAGE_IRONIC_CONFIG to the ordered service config files')
        parser.read(path)
    return parser.getboolean('conductor', 'automated_clean', fallback=None)


def set_ironic(plan=False):
    paths = ironic_files()
    ironic_policy(paths)
    path = paths[-1]
    text = path.read_text()
    sections = list(re.finditer(r'^\[([^]\n]+)\].*$', text, re.M))
    section = next((s for s in sections if s[1] == 'conductor'), None)
    if section:
        end = next((s.start() for s in sections if s.start() > section.start()), len(text))
        body = text[section.end():end]
        if re.search(r'^\s*automated_clean\s*=', body, re.M):
            body = re.sub(r'^\s*automated_clean\s*=.*$', '\nautomated_clean = false', body, flags=re.M)
        else:
            body += '\nautomated_clean = false\n'
        updated = text[:section.end()]+body+text[end:]
    else:
        updated = text+'\n[conductor]\nautomated_clean = false\n'
    if plan:
        print('Set effective conductor.automated_clean=false; service restart required if changed')
        return
    with workspace() as directory:
        temporary = Path(directory)/'ironic.conf'
        temporary.write_text(updated)
        temporary.chmod(0o600)
        if ironic_policy([*paths[:-1], temporary]) is not False:
            raise Error('Staged Ironic config does not disable automated cleaning')
        args = [arg for p in [*paths[:-1], temporary] for arg in ('--config-file', str(p))]
        # Native oslo configuration parsing and Ironic's read-only readiness check.
        run(['ironic-status', *args, 'upgrade', 'check'])
        if updated != text:
            replace(path, updated)
    print('Effective file policy validated: automated_clean=false; restart conductor to load changed configuration (no restart performed)')


def replace(path, text):
    if path.is_symlink():
        raise Error('Refuse a symbolic-link configuration target')
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix='.hwmanage-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        if path.exists():
            stat = path.stat()
            os.fchown(fd, stat.st_uid, stat.st_gid)
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def dnsmasq_path():
    path = Path(os.environ.get('HWMANAGE_DNSMASQ_INCLUDE', '/etc/dnsmasq.d/hwmanage.conf'))
    if path.name != 'hwmanage.conf':
        raise Error('Dedicated include must be named hwmanage.conf')
    if path.is_symlink():
        raise Error('Refuse a symbolic-link managed include')
    return path


def dns_records(path):
    if not path.exists():
        return {}
    text = path.read_text()
    if not text.startswith(HEADER):
        raise Error('Existing file is not the dedicated hwmanage include')
    records, name = {}, None
    for line in text[len(HEADER):].splitlines():
        if line.startswith('# host '):
            name = safe_name(line[7:])
            if name in records:
                raise Error('Duplicate managed DHCP host')
            records[name] = []
        elif name and line.startswith(('dhcp-host=', 'dhcp-option=')):
            records[name].append(line)
        elif line.strip():
            raise Error('Unrecognized managed include content; refusing to overwrite')
    return records


def dhcp_lines(name, host, options):
    name = safe_name(name)
    nexus = is_nexus(host)
    ports = [p for p in host.get('interfaces', []) if p.get('name') == 'mgmt0'] if nexus else []
    mac = options.mac
    if not mac and nexus and len(ports) == 1:
        mac = (ports[0].get('primary_mac_address') or {}).get('mac_address') or ports[0].get('mac_address')
    if not mac and not nexus and len(host.get('nics', [])) == 1:
        mac = host['nics'][0]['mac']
    if not mac or not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', mac) or mac.lower() == '00:00:00:00:00:00':
        raise Error('Exactly one valid management/provisioning MAC is required')
    address = str(ipaddress.ip_address(options.ip or host.get('ansible_host', '')))
    group = options.group or host.get('dhcp_group') or ('real-nexus-poap' if nexus else 'hwmanage')
    safe_name(group)
    lines = ['dhcp-host='+mac.lower()+',id:*,set:'+group+',set:hwmanage-'+name+','+address+','+name]
    # Actual Cisco POAP fetches poap_script.py and serial->CIDR inventory;
    # this helper never invents an image filename or overwrites that inventory.
    boot_server = options.boot_server or host.get('poap_server')
    boot_file = options.boot_file or host.get('poap_boot_file') or ('poap_script.py' if nexus else None)
    if boot_file:
        if not boot_server or not re.fullmatch(r'[A-Za-z0-9_./-]+', boot_file) or '..' in boot_file:
            raise Error('Bootfile requires a safe path and explicit boot server')
        server = str(ipaddress.ip_address(boot_server))
        lines += ['dhcp-option=tag:hwmanage-'+name+',66,'+server,
                  'dhcp-option=tag:hwmanage-'+name+',67,'+boot_file]
    return lines


def dnsmasq(action, hosts=None, options=None):
    path = dnsmasq_path()
    records = dns_records(path)
    if action == 'list-hosts':
        print('\n'.join(sorted(records)))
        return
    if any(getattr(options, k, None) for k in ('mac', 'ip')) and len(hosts) != 1:
        raise Error('Explicit MAC/IP overrides require exactly one host')
    for name, host in hosts.items():
        if action == 'add-host':
            records[name] = dhcp_lines(name, host, options)
        else:
            records.pop(name, None)
    macs = [line.split('=', 1)[1].split(',')[0] for rows in records.values() for line in rows if line.startswith('dhcp-host=')]
    if len(macs) != len(set(macs)):
        raise Error('Duplicate MAC in managed DHCP reservations')
    text = HEADER+''.join('# host '+name+'\n'+'\n'.join(records[name])+'\n' for name in sorted(records))
    if options.plan:
        print('Dedicated DHCP include: '+action+' for '+str(len(hosts))+' selected host(s)')
        return
    with workspace() as directory:
        staged = Path(directory)/'hwmanage.conf'
        staged.write_text(text)
        run(['dnsmasq', '--test', '--conf-file='+str(staged)])
    before = path.read_text() if path.exists() else None
    replace(path, text)
    try:
        run(['dnsmasq', '--test', '--conf-file='+os.environ.get('HWMANAGE_DNSMASQ_CONFIG', '/etc/dnsmasq.conf')])
    except Exception:
        if before is None:
            path.unlink()
        else:
            replace(path, before)
        raise
    print('Dedicated include validated; restart dnsmasq to load this main-config include; HUP only reloads hosts/opts data (no restart performed)')
