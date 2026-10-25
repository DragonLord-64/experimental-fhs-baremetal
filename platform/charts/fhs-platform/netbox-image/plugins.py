PLUGINS = ['netbox_inventory', 'netbox_prometheus_sd', 'netbox_topology_views']
PLUGINS_CONFIG = {'netbox_inventory': {'sync_hardware_serial_asset_tag': True}}
FIELD_CHOICES = {
    'netbox_inventory.Asset.status+': [('faulty', 'Faulty / quarantine', 'red')],
}
