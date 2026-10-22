#!/usr/bin/env python3
"""Supervisor-only scoped bootstrap; no log documents are published here."""
import argparse
import base64
import json
from pathlib import Path
import urllib.error
import urllib.request

from validate import NoRedirect

NAME = 'filebeat-fhs-one-9.5.5'


def api(url, password, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url + path, method=method, data=data,
          headers={'Authorization': 'Basic ' + base64.b64encode(('elastic:' + password).encode()).decode(),
                   'Content-Type': 'application/json'})
    with urllib.request.build_opener(NoRedirect).open(req, timeout=15) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials', type=Path, required=True)
    args = parser.parse_args()
    if args.credentials.stat().st_mode & 0o077:
        raise ValueError('private credentials required')
    private = json.loads(args.credentials.read_text())
    from urllib.parse import urlsplit
    url = private['elasticsearch_url'].rstrip('/')
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.path:
        raise ValueError('bare loopback forward required')
    def call(method, path, body=None):
        return api(url, private['bootstrap_password'], method, path, body)
    def optional(path):
        try:
            return call('GET', path)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            error.close()
            return None
    assert call('GET', '/')['version']['number'] == '9.5.5', 'version'
    # Existing publisher roles/users are preserved. Create only if absent.
    role = optional('/_security/role/filebeat_writer')
    if role is None:
        call('PUT', '/_security/role/filebeat_writer', {
            'cluster': ['monitor', 'read_ilm', 'read_pipeline'],
            'indices': [{'names': [NAME, NAME + '-*'], 'privileges': ['auto_configure', 'create_doc']}]})
    else:
        grants = role['filebeat_writer']
        assert set(grants.get('cluster', [])) <= {'monitor', 'read_ilm', 'read_pipeline'}, 'publisher cluster grants'
        assert not grants.get('run_as') and not grants.get('applications'), 'publisher extra grants'
        for grant in grants['indices']:
            assert set(grant['names']) <= {'filebeat-*', NAME, NAME + '-*'}, 'publisher index scope'
            assert set(grant['privileges']) <= {'auto_configure', 'create_doc'}, 'publisher index grants'
    user = optional('/_security/user/filebeat_writer')
    if user is None:
        call('PUT', '/_security/user/filebeat_writer', {
            'password': private['filebeat_password'], 'roles': ['filebeat_writer']})
    else:
        assert user['filebeat_writer']['roles'] == ['filebeat_writer'], 'unexpected publisher roles'
    policy = {'policy': {'phases': {
        'hot': {'actions': {'rollover': {'max_primary_shard_size': '50mb', 'max_age': '1d'}}},
        'delete': {'min_age': '2d', 'actions': {'delete': {}}}}}}
    # Refuse adoption/overwrite of preexisting differently configured owned names.
    existing = optional('/_ilm/policy/' + NAME)
    if existing:
        assert existing[NAME]['policy'] == policy['policy'], 'existing policy differs'
    else:
        call('PUT', '/_ilm/policy/' + NAME, policy)
    properties = {'@timestamp': {'type': 'date'}, 'message': {'type': 'match_only_text'},
        'host': {'properties': {'name': {'type': 'keyword'}}},
        'service': {'properties': {'name': {'type': 'keyword'}}},
        'process': {'properties': {'name': {'type': 'keyword'}, 'pid': {'type': 'long'}}},
        'event': {'properties': {'id': {'type': 'keyword'}, 'dataset': {'type': 'keyword'},
                                 'original': {'type': 'keyword', 'index': False}}},
        'labels': {'properties': {'test_run': {'type': 'keyword'}}},
        'log': {'properties': {'level': {'type': 'keyword'}, 'syslog': {
            'properties': {'priority': {'type': 'long'}}}}}}
    template = {'index_patterns': [NAME + '-*'], 'priority': 501, 'template': {
        'settings': {'number_of_shards': 1, 'number_of_replicas': 0,
                     'index.lifecycle.name': NAME, 'index.lifecycle.rollover_alias': NAME},
        'mappings': {'properties': properties}}, '_meta': {'owner': 'fhs-one-server-log-fixture'}}
    existing = optional('/_index_template/' + NAME)
    if existing:
        current = existing['index_templates'][0]['index_template']
        for key in ('index_patterns', 'priority', '_meta'):
            assert current[key] == template[key], 'existing template differs'
        assert current['template']['mappings'] == template['template']['mappings'], 'existing mappings differ'
        settings = current['template']['settings'].get('index', {})
        assert str(settings.get('number_of_shards')) == '1', 'existing shard count'
        assert str(settings.get('number_of_replicas')) == '0', 'existing replicas'
        assert settings.get('lifecycle') == {'name': NAME, 'rollover_alias': NAME}, 'existing lifecycle differs'
    else:
        call('PUT', '/_index_template/' + NAME, template)
    alias = optional('/_alias/' + NAME)
    if alias:
        assert all(index.startswith(NAME + '-') for index in alias), 'unexpected alias target'
        assert sum(item['aliases'][NAME].get('is_write_index', False) for item in alias.values()) == 1, 'write alias'
    else:
        call('PUT', '/' + NAME + '-000001', {'aliases': {NAME: {'is_write_index': True}}})
    print(json.dumps({'scoped_bootstrap_passed': True, 'destination': NAME,
                      'publishing_user': 'filebeat_writer', 'documents_injected': 0}))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
        raise SystemExit(1)
