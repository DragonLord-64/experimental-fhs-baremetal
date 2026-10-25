"""Optional server-info schema; does not rewrite the host file."""
from ansible.errors import AnsibleFilterError


def server_metadata(value):
    if value is None: value = {}
    if not isinstance(value, dict): raise AnsibleFilterError('server-info must be a mapping')
    value = dict(value)
    for key in ('site', 'role', 'location', 'rack'):
        if key in value and (not isinstance(value.get(key), str) or not value[key].strip()):
            raise AnsibleFilterError('server-info placement fields must be nonempty strings when provided')
        if key in value: value[key] = value[key].strip()
    if 'rack_unit' in value:
        unit = value['rack_unit']
        if not isinstance(unit, int) or isinstance(unit, bool) or unit < 1: raise AnsibleFilterError('rack_unit must be a positive integer')
    if 'power_ports' in value:
        ports = value['power_ports']
        if not isinstance(ports, list): raise AnsibleFilterError('power_ports must be a list')
        names = set(); outlets = set(); normalized = []
        for inlet in ports:
            if not isinstance(inlet, dict) or set(inlet) != {'name', 'pdu_serial', 'pdu_port'}:
                raise AnsibleFilterError('Each power inlet requires exactly name, pdu_serial and pdu_port')
            if any(not isinstance(v, str) or not v.strip() for v in inlet.values()):
                raise AnsibleFilterError('Power inlet identities must be nonempty strings; quote outlet numbers')
            inlet = {k: v.strip() for k, v in inlet.items()}
            outlet = (inlet['pdu_serial'], inlet['pdu_port'])
            if inlet['name'] in names or outlet in outlets: raise AnsibleFilterError('Duplicate power inlet or outlet identity')
            names.add(inlet['name']); outlets.add(outlet); normalized.append(inlet)
        value['power_ports'] = normalized
    return value


class FilterModule:
    def filters(self): return dict(fhs_server_metadata=server_metadata)
