"""Run in NetBox Django shell after acceptance_topology.py; synthetic objects only."""
import json
import os
import re
from importlib.metadata import version
from urllib.parse import urlencode
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client
from django.urls import reverse
from dcim.models import Device


@transaction.atomic
def probe():
    prefix = os.environ['FHS_TOPOLOGY_PREFIX']
    assert prefix.startswith('SYN-TOPO-')
    devices = list(Device.objects.filter(name__startswith=prefix).order_by('pk'))
    assert len(devices) == 2
    user = get_user_model().objects.filter(is_superuser=True, is_active=True).first()
    assert user is not None
    client = Client(HTTP_HOST='localhost')
    client.force_login(user)
    query = [('id', str(d.pk)) for d in devices] + [('show_cables', 'True'), ('show_unconnected', 'True')]
    response = client.get(reverse('plugins:netbox_topology_views:home') + '?' + urlencode(query))
    assert response.status_code == 200
    match = re.search(r'<script id="topology-data" type="application/json">(.*?)</script>', response.content.decode(), re.S)
    assert match, 'Topology Views graph data absent'
    graph = json.loads(match.group(1))
    ids = {str(d.pk) for d in devices}
    assert ids <= {str(n['id']) for n in graph['nodes']}
    assert any({str(e['from']), str(e['to'])} == ids for e in graph['edges']), 'Imported cable absent from topology graph'
    transaction.set_rollback(True)
    print('FHS_IMPORTED_TOPOLOGY=' + json.dumps(dict(prefix=prefix, inventory_version=version('netbox-inventory'),
        topology_version=version('netbox-topology-views'), imported_connection_visible=True)))


probe()
