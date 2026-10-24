# NetBox launcher fixture

`launch-netbox.sh` is the unchanged file from the chart's pinned image,
`ghcr.io/netbox-community/netbox@sha256:fa7ffa268c39fb258bed80bd256360a525f1a129ee4ee06298f10d6708578eba`.
Exported on `dragonvm`, 2026-10-23, with the cached image and no network:

```bash
docker run --rm --pull=never --network=none --read-only \
  --entrypoint /bin/cat fa7ffa268c39 /opt/netbox/launch-netbox.sh
```

File SHA256: `cb611e3efb743f442a48d692196be3498c3505cd8a79d53b716815aabe5fa111`.
The delivered Inventory image extends this exact base without changing the launcher.
The regression checks the build recipe and selected image. Refresh the fixture
and assertion together when changing the base or modifying its launcher.

The regression executes rendered chart commands and this launcher, replacing
only the image entrypoint and Granian with local capture stubs. It checks the
effective static route and preserved startup arguments; it does not test actual
HTTP serving, migrations, or the real entrypoint's initialization.
