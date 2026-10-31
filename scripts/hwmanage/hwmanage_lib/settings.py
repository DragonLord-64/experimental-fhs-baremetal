"""One non-secret controller configuration shared by CLI and Ansible lookups."""
from contextlib import contextmanager
import os
from pathlib import Path
from urllib.parse import urlsplit
from .common import Error, yaml_load

DEFAULT = Path(__file__).resolve().parents[1] / 'config.yml'
SCHEMA = {
    'ironic': {'endpoint', 'auth_type', 'cloud', 'config_files'},
    'platform': {'endpoints_file', 'secrets_file'},
    'credentials': {'bmc_file', 'vault_password_file'},
    'inventory': {'default', 'site_variables'},
    'bifrost': {'playbooks_directory'},
    'import': {'new_device_defaults', 'system_fru_id', 'provisioning_interface'},
    'timeouts': {'node_operation', 'ansible'},
    'checks': {'boot_url', 'services'},
    'dnsmasq': {'config_file', 'include_file'},
}
PATHS = {'platform': ('endpoints_file', 'secrets_file'),
         'credentials': ('bmc_file', 'vault_password_file'),
         'inventory': ('site_variables',), 'bifrost': ('playbooks_directory',),
         'dnsmasq': ('config_file', 'include_file')}


def load(path=None):
    source = Path(path or os.environ.get('HWMANAGE_CONFIG_FILE') or DEFAULT).resolve()
    try:
        values = yaml_load(source)
    except Exception:
        raise Error('Unable to read hwmanage configuration: '+str(source)) from None
    if not isinstance(values, dict) or set(values) != set(SCHEMA):
        raise Error('Config must contain exactly these sections: '+', '.join(SCHEMA))
    for section, keys in SCHEMA.items():
        if not isinstance(values[section], dict) or set(values[section]) != keys:
            raise Error('Invalid or missing config keys in '+section+'; expected '+', '.join(sorted(keys)))
    for section, keys in PATHS.items():
        for key in keys:
            value = values[section][key]
            if value is None and (section, key) == ('credentials', 'vault_password_file'):
                continue
            if not isinstance(value, str) or not value:
                raise Error(section+'.'+key+' must be a path')
            values[section][key] = str((source.parent / value).resolve())
    for key, minimum in [('node_operation', 900), ('ansible', 1)]:
        value = values['timeouts'][key]
        if type(value) is not int or value < minimum:
            raise Error('timeouts.'+key+' must be an integer >= '+str(minimum))
    for section, key in [('ironic', 'endpoint'), ('checks', 'boot_url')]:
        value = values[section][key]
        if value is None and section == 'checks':
            continue
        if not isinstance(value, str):
            raise Error(section+'.'+key+' must be an HTTP(S) URL')
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.password:
            raise Error(section+'.'+key+' must be an HTTP(S) URL without credentials')
    defaults = values['import']['new_device_defaults']
    if not isinstance(defaults, dict) or set(defaults) != {'site', 'role', 'device_type'}:
        raise Error('import.new_device_defaults requires site, role and device_type')
    if any(v is not None and (type(v) is not int or v <= 0) for v in defaults.values()):
        raise Error('New-device IDs must be positive integers or null')
    name = values['import']['provisioning_interface']
    if name is not None and (not isinstance(name, str) or not name):
        raise Error('import.provisioning_interface must be a name or null')
    if not isinstance(values['import']['system_fru_id'], (str, int)):
        raise Error('import.system_fru_id must be a FRU identifier')
    if not isinstance(values['inventory']['default'], str) or not values['inventory']['default']:
        raise Error('inventory.default must be netbox, ironic or a YAML path')
    if values['inventory']['default'] not in ('netbox', 'ironic'):
        values['inventory']['default'] = str((source.parent / values['inventory']['default']).resolve())
    for section, key in [('ironic', 'config_files'), ('checks', 'services')]:
        value = values[section][key]
        if not isinstance(value, list) or not value or any(not isinstance(v, str) or not v for v in value):
            raise Error(section+'.'+key+' must be a nonempty list of strings')
    values['ironic']['config_files'] = [str((source.parent / p).resolve()) for p in values['ironic']['config_files']]
    if not isinstance(values['ironic']['auth_type'], str) or not values['ironic']['auth_type']:
        raise Error('ironic.auth_type must be a string')
    if values['ironic']['cloud'] is not None and not isinstance(values['ironic']['cloud'], str):
        raise Error('ironic.cloud must be a cloud name or null')
    return source, values


def import_settings(values):
    return dict(values['import']['new_device_defaults'],
                system_fru_id=str(values['import']['system_fru_id']),
                provisioning_interface=values['import']['provisioning_interface'])


def environment(source, values):
    """Translate YAML for native applications; operators need no shell exports."""
    result = {
        'HWMANAGE_CONFIG_FILE': str(source),
        'OS_ENDPOINT': values['ironic']['endpoint'], 'OS_AUTH_TYPE': values['ironic']['auth_type'],
        'OS_CLOUD': values['ironic']['cloud'] or '',
        'FHS_PLATFORM_ENDPOINTS_FILE': values['platform']['endpoints_file'],
        'FHS_PLATFORM_SECRETS_FILE': values['platform']['secrets_file'],
        'HWMANAGE_BMC_SECRETS': values['credentials']['bmc_file'],
        'HWMANAGE_SITE_INVENTORY': values['inventory']['site_variables'],
        'HWMANAGE_BIFROST_PLAYBOOKS': values['bifrost']['playbooks_directory'],
        'HWMANAGE_TIMEOUT': str(values['timeouts']['node_operation']),
        'HWMANAGE_ANSIBLE_TIMEOUT': str(values['timeouts']['ansible']),
        'HWMANAGE_IRONIC_CONFIG': os.pathsep.join(values['ironic']['config_files']),
        'HWMANAGE_DNSMASQ_CONFIG': values['dnsmasq']['config_file'],
        'HWMANAGE_DNSMASQ_INCLUDE': values['dnsmasq']['include_file'],
        'HWMANAGE_SERVICES': ' '.join(values['checks']['services']),
        'HWMANAGE_BOOT_URL': values['checks']['boot_url'] or '',
    }
    if values['credentials']['vault_password_file']:
        result['ANSIBLE_VAULT_PASSWORD_FILE'] = values['credentials']['vault_password_file']
    return result


@contextmanager
def activated(path=None):
    source, values = load(path)
    updates = environment(source, values)
    previous = {key: os.environ.get(key) for key in {*updates, 'ANSIBLE_VAULT_PASSWORD_FILE'}}
    if not values['credentials']['vault_password_file']:
        os.environ.pop('ANSIBLE_VAULT_PASSWORD_FILE', None)
    os.environ.update(updates)
    try:
        yield values
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def validate_paths(values):
    for section, keys in PATHS.items():
        for key in keys:
            value = values[section][key]
            if value is None or (section, key) == ('dnsmasq', 'include_file'):
                continue
            path = Path(value)
            present = path.is_dir() if section == 'bifrost' else path.is_file()
            if not present:
                raise Error('Configured path unavailable: '+section+'.'+key+' ('+value+')')

    for value in values['ironic']['config_files']:
        if not Path(value).is_file():
            raise Error('Configured path unavailable: ironic.config_files ('+value+')')
