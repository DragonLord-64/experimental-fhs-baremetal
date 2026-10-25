"""Executed inside the delivered NetBox web container; emits sanitized evidence only."""
import json
import os
import re
from importlib.metadata import version
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.migrations.executor import MigrationExecutor
from django.db import connection
from django.test import Client
from django.urls import reverse
from dcim.models import Cable, Device, Interface

@transaction.atomic
def probe():
    assert version('netbox-topology-views') == '5.0.0'
    executor = MigrationExecutor(connection)
    assert not executor.migration_plan(executor.loader.graph.leaf_nodes('netbox_topology_views'))
    image_dir = Path(settings.STATIC_ROOT) / 'netbox_topology_views/img'
    assert image_dir.is_dir() and os.access(image_dir, os.W_OK)
    user = get_user_model().objects.filter(is_superuser=True, is_active=True).first()
    assert user is not None
    # Synthetic objects exist only in this rolled-back transaction, including on failure.
    seed = Device.objects.select_related('site', 'role', 'device_type').first()
    assert seed is not None, 'Retained lab inventory is required'
    devices = [Device.objects.create(name='fhs-topology-smoke-' + str(i), site=seed.site,
               role=seed.role, device_type=seed.device_type, status='active') for i in range(2)]
    interfaces = [Interface.objects.create(device=d, name='smoke', type='1000base-t') for d in devices]
    cable = Cable(a_terminations=[interfaces[0]], b_terminations=[interfaces[1]], status='connected')
    cable.save()
    ids = [d.pk for d in devices]
    client = Client(HTTP_HOST='localhost')
    client.force_login(user)
    path = reverse('plugins:netbox_topology_views:home')
    query = [('id', str(i)) for i in ids] + [('show_cables', 'True'), ('show_unconnected', 'True')]
    from urllib.parse import urlencode
    response = client.get(path + '?' + urlencode(query))
    assert response.status_code == 200, 'Authenticated topology page did not return HTTP 200'
    html = response.content.decode()
    match = re.search(r'<script id="topology-data" type="application/json">(.*?)</script>', html, re.S)
    assert match, 'No actual topology data in authenticated page'
    data = json.loads(match.group(1))
    node_ids = {str(n['id']) for n in data['nodes']}
    assert set(map(str, ids)) <= node_ids
    assert any({str(e['from']), str(e['to'])} == set(map(str, ids)) for e in data['edges']), 'Fixture connection absent'
    assets = []
    for kind, suffix in [('css', 'css/app.css'), ('js', 'js/app.js')]:
        relative = 'netbox_topology_views/' + suffix
        asset = Path(settings.STATIC_ROOT) / relative
        assert asset.is_file() and asset.stat().st_size > 100
        url = settings.STATIC_URL + relative
        assert url in html
        assets.append({'kind': kind, 'url': url, 'bytes': asset.stat().st_size})
    transaction.set_rollback(True)
    print('FHS_TOPOLOGY_RESULT=' + json.dumps({'version': version('netbox-topology-views'),
          'migrations_complete': True, 'authenticated_page': path, 'static_directory_writable': True,
          'assets': assets, 'fixture': {'devices': ids, 'cable': cable.pk, 'connection_verified': True, 'rolled_back': True}}))

probe()
