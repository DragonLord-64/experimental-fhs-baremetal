#!/usr/bin/env python3
"""Portable inventory JSON transfer. Never deletes; reports incomplete transfers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urljoin, urlsplit

import requests
import yaml

# Reviewed against NetBox 4.7 serializers/OPTIONS on the delivered chart.
# Explicit natural keys deliberately refuse names which are not unique in scope.
KEYS = {}
for app, names in {
    'dcim': 'regions site-groups sites manufacturers device-roles platforms rack-roles rack-types virtual-chassis module-type-profiles inventory-item-roles cable-bundles',
    'tenancy': 'tenant-groups tenants',
    'ipam': 'roles rirs aggregates vlan-groups vrfs',
    'extras': 'tags custom-field-choice-sets custom-fields',
}.items():
    for name in names.split():
        KEYS[f'{app}/{name}/'] = ('name',)
KEYS.update({
    'ipam/vrfs/': ('name', 'rd'),
    'ipam/aggregates/': ('prefix',),
    'ipam/vlans/': ('group', 'vid', 'name'),
    'ipam/prefixes/': ('prefix', 'vrf'),
    'dcim/locations/': ('site', 'parent', 'name'),
    'dcim/racks/': ('site', 'location', 'name'),
    'dcim/device-types/': ('manufacturer', 'model'),
    'dcim/module-types/': ('manufacturer', 'model'),
    'dcim/devices/': ('site', 'name'),
    'dcim/modules/': ('device', 'module_bay'),
    'dcim/inventory-items/': ('device', 'parent', 'name'),
    'dcim/mac-addresses/': ('mac_address',),
    'ipam/ip-addresses/': ('vrf', 'address'),
    'dcim/cables/': ('a_terminations', 'b_terminations'),
})
COMPONENTS = ('interfaces console-ports console-server-ports power-ports power-outlets '
              'front-ports rear-ports device-bays module-bays inventory-items').split()
for component in COMPONENTS:
    KEYS.setdefault(f'dcim/{component}/', ('device', 'name'))
    if component != 'inventory-items':
        KEYS[f'dcim/{component[:-1]}-templates/'] = ('device_type', 'module_type', 'name')
MODELS = dict(zip(
    ('site location rack manufacturer devicerole platform rackrole racktype virtualchassis '
     'devicetype moduletype device module inventoryitem interface consoleport consoleserverport '
     'powerport poweroutlet frontport rearport devicebay modulebay macaddress cable').split(),
    ('sites locations racks manufacturers device-roles platforms rack-roles rack-types virtual-chassis '
     'device-types module-types devices modules inventory-items interfaces console-ports console-server-ports '
     'power-ports power-outlets front-ports rear-ports device-bays module-bays mac-addresses cables').split()))
CT = {'dcim.'+k: 'dcim/'+v+'/' for k, v in MODELS.items()}
CT.update({'ipam.ipaddress': 'ipam/ip-addresses/', 'ipam.vrf': 'ipam/vrfs/',
           'ipam.vlan': 'ipam/vlans/', 'tenancy.tenant': 'tenancy/tenants/'})
RELATIONS = {'tags': 'extras/tags/', 'tagged_vlans': 'ipam/vlans/'}
DEFER = {'primary_ip4', 'primary_ip6', 'oob_ip', 'primary_mac_address', 'parent', 'bridge', 'lag', 'nat_inside'}
OPAQUE = {'local_context_data', 'data', 'constraints', 'extra_choices',
          'related_object_filter', 'validation_schema', 'schema'}


class TransferError(Exception):
    pass


def stable(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def scalar(value):
    if isinstance(value, dict):
        return value.get('id', value.get('value', value))
    if isinstance(value, list):
        return [scalar(v) for v in value]
    return value


def private_json(path, value):
    """Exclusive creation prevents symlink following and insecure old-file reuse."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def credentials(path, vault_args=()):
    try:
        # ansible-vault understands both whole-file and inline Vault encryption.
        # DataLoader supports inline values; the CLI supports password/identity prompts.
        raw = Path(path).read_bytes()
        if raw.startswith(b'$ANSIBLE_VAULT'):
            result = subprocess.run(['ansible-vault', 'view', *vault_args, str(path)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
            if result.returncode:
                raise TransferError('Vault decryption failed; check Ansible Vault identity/password access')
            raw = result.stdout
        if b'!vault' in raw:
            from ansible.parsing.dataloader import DataLoader
            from ansible.cli import CLI
            loader = DataLoader()
            secrets = CLI.setup_vault_secrets(loader, vault_ids=list(vault_args_to_ids(vault_args)),
                                               auto_prompt=False)
            loader.set_vault_secrets(secrets)
            values = loader.load(raw.decode())
        else:
            values = yaml.safe_load(raw)
        url, token = str(values['netbox_url']), str(values['netbox_token'])
        verify = values.get('netbox_validate_certs', values.get('netbox_validate_certs_default', True))
        if '{{' in str(verify):
            raise TransferError('Certificate setting must be resolved before use')
        if isinstance(verify, str):
            if verify.lower() not in ('true', 'false', 'yes', 'no', '1', '0'):
                raise TransferError('Certificate setting must be a YAML boolean')
            verify = verify.lower() in ('true', 'yes', '1')
        if not isinstance(verify, bool) or not token or '{{' in url or '{{' in token:
            raise TransferError('Credentials must contain resolved URL/token and a boolean certificate setting')
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
            raise TransferError('Invalid NetBox base URL')
        return url, token, verify
    except TransferError:
        raise
    except (ImportError, FileNotFoundError):
        raise TransferError('Credentials unavailable; install the existing Ansible requirements for Vault support') from None
    except Exception:
        raise TransferError('Unable to load YAML credentials or decrypt Vault values; no credential details logged') from None


def vault_args_to_ids(args):
    for i in range(0, len(args), 2):
        yield args[i+1] if args[i] == '--vault-id' else 'default@'+args[i+1]


class API:
    def __init__(self, url, token, verify):
        self.base = url.rstrip('/')+'/api/'
        self.session = requests.Session()
        self.session.verify = verify
        self.session.headers['Authorization'] = ('Bearer ' if token.startswith('nbt_') else 'Token ')+token
        self.cache = {}

    def request(self, method, path, **kwargs):
        if method not in ('GET', 'OPTIONS', 'POST', 'PATCH'):
            raise TransferError('HTTP method prohibited')
        url = urljoin(self.base, path)
        if not url.startswith(self.base) or urlsplit(url).netloc != urlsplit(self.base).netloc:
            raise TransferError('Foreign or out-of-prefix API URL refused')
        try:
            response = self.session.request(method, url, timeout=30, allow_redirects=False, **kwargs)
            if not response.ok or response.is_redirect:
                bad_fields = []
                if response.status_code == 400 and isinstance(kwargs.get('json'), dict):
                    try:
                        errors = response.json()
                        if isinstance(errors, dict):
                            bad_fields = sorted(k for k in errors if k in set(kwargs['json']) | {'non_field_errors', 'slug', 'name', 'address', 'mac_address', 'assigned_object', 'assigned_object_id', 'assigned_object_type', 'detail'})
                    except ValueError:
                        pass
                raise TransferError(f'NetBox {method} HTTP {response.status_code}; rejected fields: '+', '.join(bad_fields)+'; inspect validation privately')
            return response.json()
        except requests.RequestException:
            raise TransferError('API connection failed; check URL, TLS and reachability privately') from None
        except ValueError:
            raise TransferError('API did not return JSON') from None

    def rows(self, path, fresh=False):
        if not fresh and path in self.cache:
            return self.cache[path]
        rows, seen, page = [], set(), path+'?limit=100'
        while page:
            if page in seen:
                raise TransferError('Repeated pagination URL')
            seen.add(page)
            data = self.request('GET', page)
            rows.extend(data['results'])
            page = data.get('next')
        self.cache[path] = rows
        return rows

    def fields(self, path):
        fields = self.request('OPTIONS', path).get('actions', {}).get('POST')
        if not fields:
            raise TransferError('Writable schema unavailable at '+path+'; check permissions/version')
        return fields


def ref_path(value):
    if not isinstance(value, dict) or not value.get('url'):
        return None
    parts = urlsplit(value['url']).path.split('/api/', 1)
    if len(parts) == 2:
        return parts[1].rsplit('/', 2)[0]+'/'
    return None


class Exporter:
    def __init__(self, api):
        self.api, self.raw, self.fields, self.identities = api, {}, {}, {}
        self.issues, self.readonly = [], {}
        self.building = set()

    def issue(self, path, field, reason):
        item = dict(path=path, field=field, reason=reason)
        if item not in self.issues:
            self.issues.append(item)

    def reference(self, path, number):
        if path not in self.raw or number not in self.raw[path]:
            raise TransferError('Reference outside supported/exported inventory: '+str(path))
        row = self.raw[path][number]
        key = self.identity(path, row)
        return {'$ref': hashlib.sha256((path+stable(key)).encode()).hexdigest()}

    def identity(self, path, row):
        index = (path, row['id'])
        if index in self.identities:
            return self.identities[index]
        if index in self.building:
            raise TransferError('Cyclic natural identity at '+path)
        self.building.add(index)
        try:
            key = {k: self.encode(path, k, row.get(k), row) for k in KEYS[path]}
            if 'name' in key and not key['name']:
                raise TransferError('Unnamed object has no safe natural identity at '+path)
            self.identities[index] = key
            return key
        finally:
            self.building.remove(index)

    def encode(self, path, field, value, row):
        if value is None:
            return None
        if field == 'default' and path == 'extras/custom-fields/':
            if scalar(row.get('type')) in ('object', 'multiobject') and value:
                raise TransferError('Object custom-field defaults require a target adapter')
            return {'$literal': value}
        if field in OPAQUE:
            return {'$literal': value}
        if field == 'custom_fields':
            definitions = {r['name']: r for r in self.raw.get('extras/custom-fields/', {}).values()}
            result = {}
            for name, val in value.items():
                definition = definitions.get(name)
                if not definition:
                    raise TransferError('Custom field definition unavailable: '+name)
                kind = scalar(definition.get('type'))
                if kind in ('object', 'multiobject') and val is not None:
                    target = CT.get(scalar(definition.get('related_object_type')))
                    if not target:
                        raise TransferError('Unsupported object custom field target: '+name)
                    result[name] = ([self.reference(target, scalar(v)) for v in val] if kind == 'multiobject'
                                    else self.reference(target, scalar(val)))
                else:
                    result[name] = {'$literal': val}
            return result
        if field.endswith('_id') and field not in ('part_id', 'channel_id'):
            target = CT.get(scalar(row.get(field[:-3]+'_type')))
            if not target:
                raise TransferError('Unsupported generic assignment type: '+field)
            return self.reference(target, value)
        if field in ('a_terminations', 'b_terminations'):
            result = []
            for term in value:
                target = CT.get(term['object_type'])
                if not target:
                    raise TransferError('Unsupported cable termination type')
                result.append(dict(object_type=term['object_type'],
                                   object_id=self.reference(target, term.get('object_id', scalar(term.get('object'))))))
            return sorted(result, key=stable)
        if isinstance(value, list):
            if not value:
                return []
            if field in RELATIONS:
                return [self.reference(RELATIONS[field], scalar(v)) for v in value]
            # Choice sets have writable nested JSON lists; preserve them verbatim.
            if field in ('object_types', 'extra_choices', 'default'):
                return {'$literal': value}
            return [self.encode(path, field, v, row) for v in value]
        target = ref_path(value)
        if target:
            return self.reference(target, value['id'])
        if isinstance(value, dict):
            if 'value' in value:
                return value['value']
            if 'id' in value:
                raise TransferError('Relationship without portable API URL')
            raise TransferError('Unclassified nested writable data; requires schema adapter')
        meta = self.fields.get(path, {}).get(field, {})
        if meta.get('type') == 'nested object' or (meta.get('type') == 'field' and isinstance(value, int) and not isinstance(value, bool)):
            raise TransferError('Unclassified numeric relationship; refuses source ID reuse')
        return value

    def run(self, devices=()):
        status = self.api.request('GET', 'status/')
        for path in KEYS:
            try:
                self.fields[path] = self.api.fields(path)
                self.raw[path] = {r['id']: r for r in self.api.rows(path)}
            except TransferError as error:
                self.issue(path, '*', str(error))
        records, duplicates = [], set()
        for path, rows in self.raw.items():
            self.readonly[path] = sorted(k for k, v in self.fields[path].items() if v.get('read_only'))
            for row in rows.values():
                try:
                    key = self.identity(path, row)
                    rid = self.reference(path, row['id'])['$ref']
                    if rid in duplicates:
                        raise TransferError('Ambiguous source natural key at '+path)
                    duplicates.add(rid)
                    data = {}
                    for field, meta in self.fields[path].items():
                        if meta.get('read_only') or field not in row:
                            continue
                        if path == 'dcim/interfaces/' and field == 'mac_address' and 'primary_mac_address' in row:
                            continue  # legacy compatibility alias, derived from primary MAC
                        try:
                            data[field] = self.encode(path, field, row[field], row)
                        except TransferError as error:
                            self.issue(path, field, str(error))
                    records.append(dict(ref=rid, path=path, key=key, data=data))
                except TransferError as error:
                    self.issue(path, '*', str(error))
        if devices:
            selected = {r['ref'] for r in records if r['path'] == 'dcim/devices/' and r['data'].get('name') in devices}
            found = {r['data'].get('name') for r in records if r['ref'] in selected}
            if found != set(devices):
                raise TransferError('Selected device missing or unsupported; check names')
            # Definitions and choice sets must enter the dependency closure too.
            selected.update(r['ref'] for r in records if r['path'].startswith('extras/custom-field'))
            # Include installations and cables attached to selection, then all dependencies.
            changed = True
            while changed:
                before = set(selected)
                for r in records:
                    parent = r['data'].get('device')
                    if isinstance(parent, dict) and parent.get('$ref') in selected:
                        selected.add(r['ref'])
                    if r['path'].endswith('-templates/') and any(
                        isinstance(r['data'].get(k), dict) and r['data'][k].get('$ref') in selected
                        for k in ('device_type', 'module_type')
                    ):
                        selected.add(r['ref'])
                    assignment = r['data'].get('assigned_object_id')
                    if isinstance(assignment, dict) and assignment.get('$ref') in selected:
                        selected.add(r['ref'])
                    if r['path'] == 'dcim/cables/' and references(r['data']) & selected:
                        selected.add(r['ref'])
                    if r['ref'] in selected:
                        selected.update(references(r['data']))
                changed = before != selected
            # Custom fields are global definitions, including unused definitions.
            records = [r for r in records if r['ref'] in selected or r['path'].startswith('extras/custom-field')]
        plugins = status.get('plugins', {})
        if plugins:
            self.issue('plugins/', '*', 'Plugin objects unsupported (including Inventory assets, item types/groups, roles, suppliers, purchases, deliveries and audits); installed plugins: '+', '.join(sorted(plugins)))
        return dict(format='fhs-netbox-inventory', version=1, source=status,
                    records=records, readonly=self.readonly, issues=self.issues)


def references(value):
    if isinstance(value, dict):
        if '$literal' in value:
            return set()
        if set(value) == {'$ref'}:
            return {value['$ref']}
        return set().union(*(references(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(references(v) for v in value))
    return set()


def resolve(value, mapping):
    if isinstance(value, dict):
        if set(value) == {'$literal'}:
            return value['$literal']
        if set(value) == {'$ref'}:
            if value['$ref'] not in mapping:
                raise TransferError('Unresolved portable reference '+value['$ref'][:12])
            return mapping[value['$ref']]
        return {k: resolve(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, mapping) for v in value]
    return value


def comparable(value):
    if isinstance(value, list):
        return sorted((comparable(v) for v in value), key=stable)
    if isinstance(value, dict):
        if 'id' in value or 'value' in value:
            return scalar(value)
        return {k: comparable(v) for k, v in value.items()}
    return value


def termination_key(row):
    return {side: sorted((dict(object_type=t['object_type'], object_id=t.get('object_id', scalar(t.get('object'))))
                         for t in row.get(side, [])), key=stable)
            for side in ('a_terminations', 'b_terminations')}


class Importer:
    def __init__(self, api, preview=False):
        self.api, self.preview, self.mapping, self.schemas = api, preview, {}, {}
        self.actions, self.issues = [], []
        self.virtual = -1

    def schema(self, path):
        if path not in self.schemas:
            self.schemas[path] = self.api.fields(path)
        return self.schemas[path]

    def match(self, path, key):
        rows = self.api.rows(path)
        matches = [r for r in rows if all(comparable((str(r.get(k)).upper() if path == 'dcim/mac-addresses/' and k == 'mac_address' else
                                                    (termination_key(r) if path == 'dcim/cables/' else r).get(k))) == comparable(v)
                                        for k, v in key.items())]
        if len(matches) > 1:
            raise TransferError('Ambiguous destination identity; disambiguate '+path)
        return matches[0] if matches else None

    def guard(self, path, old, data):
        if old and path in ('ipam/ip-addresses/', 'dcim/mac-addresses/'):
            before = (scalar(old.get('assigned_object_type')), old.get('assigned_object_id'))
            after = (data.get('assigned_object_type', before[0]), data.get('assigned_object_id', before[1]))
            if before[1] is not None and after != before:
                raise TransferError('Occupied IP/MAC ownership preserved; resolve assignment privately')
        if path == 'dcim/cables/':
            if old and termination_key(old) != termination_key(data):
                raise TransferError('Existing cable terminations preserved')
            for side in ('a_terminations', 'b_terminations'):
                for term in data.get(side, []):
                    target = CT.get(term['object_type'])
                    if not target:
                        raise TransferError('Unsupported cable termination')
                    endpoint = next((r for r in self.api.rows(target) if r['id'] == term['object_id']), None)
                    if not endpoint:
                        raise TransferError('Missing cable endpoint; import its component first')
                    occupied = scalar(endpoint.get('cable'))
                    if (occupied and (not old or occupied != old['id'])) or endpoint.get('mark_connected'):
                        raise TransferError('Occupied cable endpoint preserved; review cable/mark_connected')

    def apply(self, record, deferred=False):
        path = record['path']
        key = resolve(record['key'], self.mapping)
        if path == 'dcim/mac-addresses/' and key.get('mac_address'):
            key['mac_address'] = key['mac_address'].upper()
        old = self.match(path, key)
        schema = self.schema(path)
        fields, waiting = {}, []
        for field, value in record['data'].items():
            if field not in schema or schema[field].get('read_only'):
                raise TransferError('Destination field unavailable/read-only: '+field)
            if value is not None and (schema[field].get('type') == 'nested object' or (field.endswith('_id') and field not in ('part_id', 'channel_id'))):
                if not isinstance(value, dict) or set(value) != {'$ref'}:
                    raise TransferError('Relationship requires a portable reference: '+field)
            if value and field in RELATIONS:
                if not isinstance(value, list) or any(not isinstance(v, dict) or set(v) != {'$ref'} for v in value):
                    raise TransferError('Relationship list requires portable references: '+field)
            try:
                fields[field] = resolve(value, self.mapping)
            except TransferError:
                if not deferred and not (field.endswith('_id') and field not in ('part_id', 'channel_id')) and (field in DEFER or not schema[field].get('required')):
                    waiting.append(field)
                else:
                    raise
        if deferred and waiting:
            raise TransferError('Unresolved deferred relationships')
        if path == 'dcim/mac-addresses/' and fields.get('mac_address'):
            fields['mac_address'] = fields['mac_address'].upper()
        self.guard(path, old, fields)
        # Cable.profile is emitted as null on unprofiled 4.7 cables, although its
        # serializer rejects null/blank input. Omit only when creating the default;
        # attempts to clear an existing profile remain a reported API failure.
        if path == 'dcim/cables/' and not old and fields.get('profile') is None:
            fields.pop('profile', None)
        # Supplied CF names update individually. {} explicitly clears all values.
        if old and fields.get('custom_fields'):
            fields['custom_fields'] = dict(old.get('custom_fields') or {}, **fields['custom_fields'])
        changes = {k: v for k, v in fields.items() if not old or
                   (old.get(k) != v if k in OPAQUE else comparable(old.get(k)) != comparable(v))}
        if old and 'custom_fields' in changes:
            encoded = record['data'].get('custom_fields', {})
            current = old.get('custom_fields') or {}
            if not encoded:
                same = all(v is None for v in current.values())
            else:
                same = all((current.get(k) == fields['custom_fields'][k] if isinstance(v, dict) and '$literal' in v
                            else comparable(current.get(k)) == comparable(fields['custom_fields'][k]))
                           for k, v in encoded.items())
            if same:
                changes.pop('custom_fields')
        if path == 'dcim/cables/' and old:
            for side in ('a_terminations', 'b_terminations'):
                if termination_key(old)[side] == fields.get(side):
                    changes.pop(side, None)
        if changes:
            self.actions.append(dict(ref=record['ref'], path=path, action='update' if old else 'create', fields=sorted(changes)))
            if self.preview:
                if old:
                    result = dict(old, **fields)
                else:
                    self.virtual -= 1
                    result = dict(fields, id=self.virtual)
                rows = self.api.rows(path)
                if old:
                    rows[rows.index(old)] = result
                else:
                    rows.append(result)
            else:
                result = self.api.request('PATCH' if old else 'POST', path+(str(old['id'])+'/' if old else ''), json=changes)
                # Device/module creation may instantiate template components.
                self.api.cache.clear()
        else:
            result = old
        if result is None:
            raise TransferError('Empty object cannot be created')
        self.mapping[record['ref']] = result['id']
        return waiting

    def run(self, document):
        if document.get('format') != 'fhs-netbox-inventory' or document.get('version') != 1:
            raise TransferError('Unsupported transfer file format/version')
        records = document['records']
        refs = [r['ref'] for r in records]
        if len(refs) != len(set(refs)):
            raise TransferError('Duplicate/ambiguous portable identities in file')
        for record in records:
            if record['path'] not in KEYS or set(record['key']) != set(KEYS[record['path']]):
                raise TransferError('Unsupported endpoint or natural key in file')
            if references(record) - set(refs):
                raise TransferError('Missing referenced record; repair export selection')
        status = self.api.request('GET', 'status/')
        self.issues.extend(document.get('issues', []))
        if status.get('netbox-version') != document.get('source', {}).get('netbox-version') or status.get('plugins') != document.get('source', {}).get('plugins'):
            self.issues.append(dict(reason='Source/destination version or plugin mismatch; review field/API compatibility'))
        pending, deferred = list(records), []
        errors = {}
        while pending:
            remaining = []
            for record in pending:
                try:
                    if self.apply(record):
                        deferred.append(record)
                    errors.pop(record['ref'], None)
                except TransferError as error:
                    errors[record['ref']] = str(error)
                    remaining.append(record)
            if len(remaining) == len(pending):
                pending = remaining
                break
            pending = remaining
        for record in deferred:
            try:
                self.apply(record, deferred=True)
            except TransferError as error:
                errors[record['ref']] = str(error)
        paths = {r['ref']: r['path'] for r in records}
        self.issues.extend(dict(ref=ref, path=paths[ref], reason=reason) for ref, reason in errors.items())
        return dict(preview=self.preview, mapped=len(self.mapping), total=len(records),
                    actions=self.actions, issues=self.issues, complete=not self.issues)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('export', 'import'))
    parser.add_argument('--vars', required=True, help='Same protected YAML vars file as the playbooks')
    parser.add_argument('--file', required=True, help='Portable JSON input/output (export requires a new path)')
    parser.add_argument('--report', help='New private JSON report file; stdout contains counts only')
    parser.add_argument('--device', action='append', default=[], help='Export named devices and connected dependencies')
    parser.add_argument('--dry-run', action='store_true', help='Import preview; GET/OPTIONS only')
    parser.add_argument('--vault-password-file', action='append', default=[])
    parser.add_argument('--vault-id', action='append', default=[])
    args = parser.parse_args()
    try:
        vault = [v for p in args.vault_password_file for v in ('--vault-password-file', p)]
        vault += [v for p in args.vault_id for v in ('--vault-id', p)]
        api = API(*credentials(args.vars, vault))
        if args.mode == 'export':
            if args.dry_run:
                raise TransferError('--dry-run is an import option; export is read-only')
            document = Exporter(api).run(args.device)
            # Never serialize the API token even if it appeared in source free text.
            token = api.session.headers['Authorization'].split(' ', 1)[1]
            if token in stable(document):
                raise TransferError('Export contains API credential text; sanitize source metadata privately')
            private_json(args.file, document)
            report = dict(objects=len(document['records']), issues=document['issues'], complete=not document['issues'])
        else:
            if args.device:
                raise TransferError('--device applies only to export')
            report = Importer(api, args.dry_run).run(json.loads(Path(args.file).read_text()))
        if args.report:
            private_json(args.report, report)
        print(stable({k: v for k, v in report.items() if k not in ('actions', 'issues')} | {'issues': len(report['issues'])}))
        return 0 if report['complete'] else 2
    except TransferError as error:
        print('Transfer failed: '+str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        # API payloads, YAML parser diagnostics and exception values can contain secrets.
        print('Transfer failed; check protected inputs, schema access and file paths. No credentials or payload logged.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
