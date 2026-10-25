# Optional NetBox image

The chart installs Inventory 2.7.1, Prometheus SD 2.2.0 and Topology Views 5.0.0
on NetBox 4.7.0 automatically. Build this image only when preinstalled plugins
are needed, for example for an offline installation.

From the chart directory:

```bash
bash netbox-image/build.sh
NETBOX_IMAGE=registry.example/team/netbox-inventory:4.7.0-2.7.1 \
  bash netbox-image/build.sh --push
```

Set `netbox.image.registry`, `repository`, `tag` and `digest` in site values.
All nodes must be able to pull it. Package pins: [requirements.txt](requirements.txt).
