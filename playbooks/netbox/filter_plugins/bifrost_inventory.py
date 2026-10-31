"""Adapt Bifrost node definitions to SSH hosts with controller-side IPMI access."""
from urllib.parse import urlsplit
from ansible.errors import AnsibleFilterError


def bifrost_import_hosts(nodes, selected=None, driver_defaults=None, ssh_user='ubuntu'):
    if not isinstance(nodes, dict) or not nodes:
        raise AnsibleFilterError('Bifrost inventory must be a nonempty node mapping')
    if not isinstance(selected or [], list) or not isinstance(driver_defaults or {}, dict):
        raise AnsibleFilterError('Use a list for bifrost_import_nodes and a mapping for driver_info defaults')
    wanted = set(selected or [])
    entries = nodes.items()
    result = []; matched = set()
    for key, node in entries:
        if not isinstance(node, dict):
            raise AnsibleFilterError('Each Bifrost node must be a mapping')
        name = node.get('name') or key
        if wanted and name not in wanted and key not in wanted:
            continue
        matched.update(wanted.intersection([name, key]))
        if not isinstance(name, str) or not name or name == 'localhost' or any(c.isspace() for c in name):
            raise AnsibleFilterError('Each selected node needs a distinct non-localhost name')
        driver = dict(driver_defaults or {})
        if not isinstance(node.get('driver_info', {}), dict):
            raise AnsibleFilterError(f'Invalid driver_info for {name}')
        driver.update(node.get('driver_info', {}))
        address = driver.get('ipmi_address')
        if not address and driver.get('redfish_address'):
            try:
                address = urlsplit(driver['redfish_address']).hostname
            except ValueError:
                raise AnsibleFilterError(f'Invalid BMC address for {name}') from None
        user = driver.get('ipmi_username', driver.get('redfish_username'))
        password = driver.get('ipmi_password', driver.get('redfish_password'))
        os_address = node.get('ansible_host') or node.get('ipv4_address')
        if not all(isinstance(v, str) and v.strip() for v in [address, user, password, os_address]):
            raise AnsibleFilterError(f'Missing OS address or BMC address/credentials for {name}')
        try:
            port = int(driver.get('ipmi_port', 623))
            if not 1 <= port <= 65535:raise ValueError()
        except (TypeError, ValueError):
            raise AnsibleFilterError(f'Invalid IPMI port for {name}') from None
        host = dict(name=name, ansible_host=os_address, ansible_connection='ssh',
                    ansible_user=node.get('ansible_user', ssh_user),
                    netbox_ipmi_address=address, netbox_ipmi_username=user,
                    netbox_ipmi_password=password, netbox_ipmi_port=port)
        for field in ('ansible_ssh_private_key_file', 'ansible_python_interpreter', 'ansible_become',
                      'ansible_become_password', 'bootstrap_site', 'bootstrap_role', 'system_fru_id'):
            if field in node:host[field] = node[field]
        result.append(host)
    if wanted - matched:
        raise AnsibleFilterError('Some bifrost_import_nodes names were not found')
    if not result:
        raise AnsibleFilterError('No Bifrost servers selected')
    for field in ('name', 'ansible_host', 'netbox_ipmi_address'):
        if len({host[field] for host in result}) != len(result):
            raise AnsibleFilterError(f'Duplicate {field} in selected Bifrost servers; correct the mapping before import')
    return result


class FilterModule:
    def filters(self):
        return {'fhs_bifrost_import_hosts': bifrost_import_hosts}
