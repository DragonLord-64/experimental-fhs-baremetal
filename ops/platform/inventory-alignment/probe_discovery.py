"""Controller executes in delivered NetBox; authenticated plugin assertions only."""
import json
import re
from importlib.metadata import version
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client
from django.urls import reverse
from dcim.models import Cable, Device, Interface, InventoryItem
from netbox_inventory.models import Asset
from urllib.parse import urlencode


def probe(expected):
    with transaction.atomic():
        prefix=expected['fixture_prefix']; assert prefix.startswith('SYN-DISC-')
        executor=MigrationExecutor(connection)
        for app in ('netbox_inventory','netbox_topology_views'):
            assert not executor.migration_plan(executor.loader.graph.leaf_nodes(app)), app+' migrations pending'
        devices=list(Device.objects.filter(pk__in=expected['device_ids']))
        assert len(devices)==len(expected['device_ids'])
        assert all(d.name.startswith(prefix) for d in devices)
        user=get_user_model().objects.filter(is_superuser=True,is_active=True).first(); assert user
        client=Client(HTTP_HOST='localhost'); client.force_login(user)
        query=[('id',str(d.pk)) for d in devices]+[('show_cables','True'),('show_unconnected','True'),('show_power','True')]
        response=client.get(reverse('plugins:netbox_topology_views:home')+'?'+urlencode(query))
        assert response.status_code==200
        match=re.search(r'<script id="topology-data" type="application/json">(.*?)</script>',response.content.decode(),re.S)
        assert match, 'Authenticated topology graph absent'
        graph=json.loads(match.group(1))
        assert set(map(str,expected['device_ids'])) <= {str(n['id']) for n in graph['nodes']}
        edges=graph['edges']
        for a,b in expected['topology_expected_pairs']:
            assert any({str(e['from']),str(e['to'])}=={str(a),str(b)} for e in edges), 'Expected device connection absent'
        # Every imported physical network cable must have its own graph evidence,
        # including DACs parallel to an ordinary LLDP connection.
        text=json.dumps(edges)
        for cable_id in expected['network_cable_ids']:
            cable=Cable.objects.get(pk=cable_id)
            assert cable.a_terminations and cable.b_terminations
            # Topology Views embeds the native cable URL in the edge title.
            assert cable.get_absolute_url() in text, 'Imported native cable absent from authenticated graph'
        item=InventoryItem.objects.get(device__name=prefix+'-HOST-A',name='C0-QSFP0 transceiver')
        asset=Asset.objects.get(inventoryitem=item)
        assert asset.serial==item.serial and item.custom_field_data['fhs_module_observation']['reported']['vendor_partnumber']=='QDD-400G-PC01'
        page=client.get(asset.get_absolute_url());assert page.status_code==200
        assert item.serial in page.content.decode(), 'Inventory asset page lacks imported identity'
        transaction.set_rollback(True)
        return dict(authenticated_topology=True,all_native_network_cables_visible=True,network_cables=len(expected['network_cable_ids']),
                    inventory_asset_page=True,inventory_version=version('netbox-inventory'),topology_version=version('netbox-topology-views'),
                    migrations_complete=True,login_transaction_rolled_back=True)
