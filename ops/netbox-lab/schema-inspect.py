"""Supervisor-only Django shell metadata probe; no records or secrets emitted."""
import json


def inspect():
    import django
    from django.apps import apps
    from django.conf import settings
    from django.db import connection, transaction
    models = ('dcim.Device', 'dcim.Module', 'dcim.ModuleBay', 'dcim.Interface',
              'dcim.InventoryItem', 'dcim.MACAddress', 'ipam.IPAddress',
              'extras.TaggedItem', 'core.ObjectChange')
    result = {'django': django.get_version(), 'netbox': str(getattr(settings, 'VERSION', 'unknown')), 'models': {}}
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
            cursor.execute("SET LOCAL statement_timeout = '5s'")
        for label in models:
            try:
                model = apps.get_model(label)
            except LookupError:
                result['models'][label] = {'available': False}
                continue
            fields = []
            for field in model._meta.get_fields():
                target = getattr(field, 'related_model', None)
                remote = getattr(field, 'remote_field', None)
                on_delete = getattr(remote, 'on_delete', None)
                fields.append({'name': field.name, 'type': type(field).__name__,
                               'null': getattr(field, 'null', None),
                               'related_model': target._meta.label_lower if target else None,
                               'on_delete': getattr(on_delete, '__name__', None)})
            result['models'][label] = {'available': True, 'fields': fields}
    return result


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True, indent=2))
