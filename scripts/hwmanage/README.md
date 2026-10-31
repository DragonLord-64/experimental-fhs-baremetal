# Hardware management

Application entry point: `scripts/hwmanage/hwmanage`. Install it inside Bifrost from the
repository root:

```bash
scripts/install-hwmanage.sh
hwmanage --help
```

Edit [import.yml](import.yml) with existing NetBox site, role and device-type IDs
and approved onboard interface names. These are tracked, non-secret settings;
credentials stay in `/provision/files.d/credentials/`.

See the [operator guide](../../docs/src/playbooks/hwmanage.md) for file formats,
credential paths and commands. Native import playbooks remain in
`playbooks/netbox/`.
