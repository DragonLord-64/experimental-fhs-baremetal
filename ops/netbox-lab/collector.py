"""Supervisor-only Django shell collector. No network client and no mutations.

Run inside the owned lab pod after independent source review. Input/output are
private files. A read-only repeatable-read transaction bounds one coherent scope.
"""
import json
import os
from itertools import islice
from pathlib import Path

MAX_ROWS = 12000


def bounded(query):
    if hasattr(query, 'model') and getattr(getattr(query.model, '_meta', None), 'label_lower', None) == 'extras.taggeditem' and not getattr(query, '_fields', None):
        query = query.select_related('content_type', 'tag')
    rows = list(query[:MAX_ROWS + 1]) if hasattr(query, 'model') else list(islice(iter(query), MAX_ROWS + 1))
    if len(rows) > MAX_ROWS:
        raise RuntimeError('Scoped collector row bound exceeded')
    return rows


def native_records(query):
    """Bounded stored-fact capture, without DRF or per-instance properties.

    All concrete fields (including future fields) are included. Relations use
    immutable IDs; only site and tag slugs are expanded for scope validation.
    Reverse one-to-one relations include Device.parent_bay on NetBox 4.7.
    Unsupported native values fail JSON encoding rather than being omitted.
    """
    fields = list(query.model._meta.concrete_fields)
    names = [field.attname for field in fields]
    reverse_relations = [rel for rel in query.model._meta.related_objects if rel.one_to_one]
    reverse = [rel.get_accessor_name() for rel in reverse_relations]
    # Review: freeze the native reverse mapping so detach reconciliation need not
    # guess installed related_names or ignore reverse safety facts.
    reverse_fields = {rel.get_accessor_name(): {
        'model': rel.related_model._meta.label_lower, 'field': rel.field.name}
        for rel in reverse_relations}
    extras = [name + '__pk' for name in reverse]
    if any(field.name == 'site' for field in fields):
        extras.append('site__slug')
    if any(field.name == 'assigned_object_type' for field in fields):
        extras.extend(['assigned_object_type__app_label', 'assigned_object_type__model'])
    rows = bounded(query.values(*(names + extras)))
    result = {}
    for values in rows:
        record = {}
        for field in fields:
            value = values[field.attname]
            name = 'custom_fields' if field.name == 'custom_field_data' else field.name
            if field.name == 'assigned_object_type':
                value = (values['assigned_object_type__app_label'] + '.' +
                         values['assigned_object_type__model']) if value is not None else None
            elif field.is_relation:
                value = {'id': value} if value is not None else None
                if field.name == 'site' and value is not None:
                    value['slug'] = values['site__slug']
            elif field.choices:
                value = {'value': value, 'label': dict(field.flatchoices).get(value, value)}
            record[name] = value
        for name in reverse:
            pk = values[name + '__pk']
            record[name] = {'id': pk} if pk is not None else None
        if reverse_fields:
            record['_prune_reverse_one_to_one'] = reverse_fields
        result[record['id']] = record
    # Review: joined values queries bound fan-out before materialization. No
    # prefetch cache or API serializer may trigger hidden per-row reads.
    for field in query.model._meta.many_to_many:
        if field.name == 'tags':
            continue
        for record in result.values():
            record[field.name] = []
        pairs = bounded(query.values('pk', field.name + '__pk').order_by('pk', field.name + '__pk'))
        for pair in pairs:
            pk = pair[field.name + '__pk']
            if pk is not None:
                result[pair['pk']][field.name].append({'id': pk})
    # NetBox's taggit manager is not necessarily a concrete ManyToManyField.
    for record in result.values():
        record['tags'] = []
    for pair in bounded(query.values('pk', 'tags__pk', 'tags__slug', 'tags__name')
                        .order_by('pk', 'tags__pk')):
        if pair['tags__pk'] is not None:
            result[pair['pk']]['tags'].append({'id': pair['tags__pk'],
                                             'slug': pair['tags__slug'],
                                             'name': pair['tags__name']})
    # Django's encoder supports native dates, UUIDs, decimals and IP values.
    from django.core.serializers.json import DjangoJSONEncoder
    class NativeEncoder(DjangoJSONEncoder):
        def default(self, value):
            # NetBox's native IP/MAC fields use netaddr value objects.
            from netaddr import IPAddress, IPNetwork, EUI, mac_unix_expanded
            if isinstance(value, EUI):
                return value.format(dialect=mac_unix_expanded)
            if isinstance(value, (IPAddress, IPNetwork)):
                return str(value)
            return super().default(value)
    return json.loads(json.dumps(list(result.values()), cls=NativeEncoder))


def validate_scope(selected_ids, scope):
    """Reject incomplete refresh scopes before importing the deployed ORM."""
    from prune import TABLES
    if (not isinstance(selected_ids, list) or (not selected_ids and scope is None)
            or len(selected_ids) > 160
            or any(type(i) is not int or i <= 0 for i in selected_ids)
            or len(set(selected_ids)) != len(selected_ids)):
        raise RuntimeError('Expected unique selected obsolete IDs, maximum 160')
    if scope is not None:
        if not isinstance(scope, dict) or set(scope) != set(TABLES):
            raise RuntimeError('Refresh requires all four frozen scope tables')
        if any(not isinstance(ids, list) or len(ids) > MAX_ROWS
               or any(type(pk) is not int or pk <= 0 for pk in ids)
               or len(set(ids)) != len(ids) for ids in scope.values()):
            raise RuntimeError('Invalid frozen scope')
        if not set(selected_ids) <= set(scope[TABLES[0]]):
            raise RuntimeError('Selected IDs outside frozen scope')


def collect(selected_ids, scope=None):
    validate_scope(selected_ids, scope)
    import django
    from django.apps import apps
    from django.conf import settings
    from django.db import connection, transaction
    from django.db.models import Q
    from django.db.models.deletion import Collector, ProtectedError, RestrictedError
    from django.contrib.contenttypes.models import ContentType
    from dcim.models import Device, Interface, MACAddress
    from ipam.models import IPAddress
    from inventory import OWNER, SITE, MARKER, tagged
    from prune import TABLES, MODELS, digest, safety_projection
    refresh = scope is not None
    scope = scope or {}
    import time
    deadline = time.monotonic() + 60
    queries = 0
    def query_budget(execute, sql, params, many, context):
        nonlocal queries
        queries += 1
        if queries > 1000 or time.monotonic() > deadline:
            raise RuntimeError('Collector query/time budget exceeded')
        return execute(sql, params, many, context)
    with connection.execute_wrapper(query_budget), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute("SET LOCAL lock_timeout = '2s'")
        # One owned-tag population read; dependencies include changed/unowned rows.
        # Review: population selection happens once; refreshes use frozen IDs,
        # including records whose ownership was changed after plan approval.
        device_filter = (Q(pk__in=scope[TABLES[0]]) if refresh else
                         Q(tags__slug=OWNER, site__slug=SITE))
        devices = bounded(Device.objects.filter(device_filter).distinct().order_by('pk'))
        selected = [r for r in devices if r.pk in selected_ids]
        ports = bounded(Interface.objects.filter(Q(device_id__in=[r.pk for r in devices]) | Q(pk__in=scope.get(TABLES[1], []))).order_by('pk'))
        ct = ContentType.objects.get_for_model(Interface)
        ips = bounded(IPAddress.objects.filter(Q(assigned_object_type=ct, assigned_object_id__in=[r.pk for r in ports]) | Q(pk__in=scope.get(TABLES[2], []))).order_by('pk'))
        macs = bounded(MACAddress.objects.filter(Q(assigned_object_type=ct, assigned_object_id__in=[r.pk for r in ports]) | Q(pk__in=scope.get(TABLES[3], []))).order_by('pk'))
        snapshot = {table: native_records(model.objects.filter(pk__in=[r.pk for r in rows]).order_by('pk'))
                    for table, model, rows in zip(TABLES, (Device, Interface, IPAddress, MACAddress),
                                                 (devices, ports, ips, macs))}
        facts = {(model, row['id']): row for table, model in zip(TABLES, MODELS)
                 for row in snapshot[table]}
        if (len(selected) != len(selected_ids) or any(
                not tagged(facts[('dcim.device', obj.pk)], OWNER) or
                facts[('dcim.device', obj.pk)]['site']['slug'] != SITE for obj in selected)):
            raise RuntimeError('Selected device missing or outside owned lab')
        pids = {p.pk for p in ports if p.device_id in selected_ids}
        targets = [selected, [p for p in ports if p.pk in pids],
                   [r for r in ips if r.assigned_object_id in pids],
                   [r for r in macs if r.assigned_object_id in pids]]
        expected = {(m, r.pk) for m, rows in zip(MODELS, targets) for r in rows}
        evidence = {'complete': True, 'device_ids': sorted(selected_ids), 'effects': [],
                    'updates': [], 'blockers': [], 'versions': {'django': django.get_version(),
                    'netbox': str(getattr(settings, 'VERSION', 'unknown'))}}
        # Explicit address-reference checks include VMs and every installed ORM
        # relation, not just retained devices. Unsupported relations block cleanup.
        for model, rows in ((IPAddress, targets[2]), (MACAddress, targets[3])):
            for relation in model._meta.related_objects:
                related = relation.related_model
                refs = bounded(related._base_manager.filter(**{relation.field.name + '__in': rows}))
                for obj in refs:
                    if (obj._meta.label_lower, obj.pk) not in expected:
                        evidence['blockers'].append({'model': obj._meta.label_lower, 'id': obj.pk,
                                                     'reason': 'external address reference'})
        # Review: bound recursive inputs before Django materializes them, including
        # generic relations. Preserve querysets for Django's later field filters.
        class BoundedCollector(Collector):
            def collect(self, objs, *args, **kwargs):
                rows = bounded(objs)
                return super().collect(rows, *args, **kwargs) if rows else None

            def related_objects(self, related_model, related_fields, objs):
                query = super().related_objects(related_model, related_fields, objs)
                ids = [obj.pk for obj in bounded(query)]
                return query.filter(pk__in=ids)

            def add(self, objs, *args, **kwargs):
                rows = bounded(objs)
                result = super().add(rows, *args, **kwargs)
                if sum(len(group) for group in self.data.values()) > MAX_ROWS:
                    raise RuntimeError('Total collector row bound exceeded')
                return result

            def add_field_update(self, field, value, objs):
                return super().add_field_update(field, value, bounded(objs))

        collector = BoundedCollector(using='default')
        try:
            collector.collect(selected)
        except (ProtectedError, RestrictedError):
            evidence['blockers'].append({'reason': 'protected or restricted relation'})
        effects = {}
        for rows in list(collector.data.values()) + list(collector.fast_deletes):
            for obj in bounded(rows):
                effects[(obj._meta.label_lower, obj.pk)] = obj
                if len(effects) > MAX_ROWS:
                    raise RuntimeError('Total collector effect bound exceeded')
        for (model, pk), obj in sorted(effects.items()):
            # Modules, inventory items, object changes/history and all unknown
            # models are deliberately forbidden even if labelled as lab-owned.
            owned = ((model, pk) in expected and
                     ((model == 'dcim.device' and obj in selected) or
                      (model in ('dcim.interface', 'ipam.ipaddress') and
                       facts[(model, pk)]['description'] == MARKER and tagged(facts[(model, pk)], OWNER)) or
                      (model == 'dcim.macaddress' and obj.description == MARKER)))
            effect = {'model': model, 'id': pk, 'owned': bool(owned)}
            # Review: only the synthetic owner's known tag assignments may
            # cascade with a selected device/interface. Manual tags block prune.
            if model == 'extras.taggeditem':
                parent_model = obj.content_type.model_class()._meta.label_lower
                effect.update(parent_model=parent_model, parent_id=obj.object_id, tag=obj.tag.slug)
                effect['owned'] = ((parent_model, obj.object_id) in expected
                                   and parent_model in MODELS[:2]
                                   and obj.tag.slug in {OWNER, 'lab-logical', 'simulated-hardware'})
            evidence['effects'].append(effect)
        for (field, value), groups in collector.field_updates.items():
            for group in groups:
                for obj in bounded(group) if hasattr(group, 'model') else group:
                    evidence['updates'].append({'model': obj._meta.label_lower, 'id': obj.pk,
                                                'field': field.name, 'null': value is None})
        if len(evidence['effects']) + len(evidence['updates']) + len(evidence['blockers']) > MAX_ROWS:
            raise RuntimeError('Total dependency evidence bound exceeded')
        evidence['facts_sha256'] = digest(safety_projection(snapshot))
        evidence['sha256'] = digest(evidence)
        snapshot['dependency_evidence'] = evidence
        return snapshot


def main():
    # Deliberately no kubectl, pod discovery, secrets or connection handling.
    selected = json.loads(Path(os.environ['FHS_PRUNE_IDS']).read_text())
    scope_path = os.environ.get('FHS_PRUNE_SCOPE')
    scope = json.loads(Path(scope_path).read_text()) if scope_path else None
    result = collect(selected, scope)
    fd = os.open(os.environ['FHS_PRUNE_OUTPUT'], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(result, output, sort_keys=True, indent=2)


if __name__ == '__main__':
    main()
