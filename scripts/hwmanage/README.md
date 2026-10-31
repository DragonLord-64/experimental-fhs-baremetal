# Hardware management

Application entry point: `scripts/hwmanage/hwmanage`. Install it inside Bifrost from the
repository root:

```bash
scripts/install-hwmanage.sh
hwmanage --help
```

Edit [config.yml](config.yml) for controller paths, endpoints, inventory and import
defaults. Set existing NetBox site, role and device-type IDs under
`import.new_device_defaults`.
Use `hwmanage config show` or `hwmanage config validate` to inspect settings.
The provisioning interface is selected from the inspected boot MAC. These are
tracked, non-secret settings;
credentials stay in `/provision/files.d/credentials/`.

See the [operator guide](../../docs/src/playbooks/hwmanage.md) for file formats,
credential paths and commands. Native import playbooks remain in
`playbooks/netbox/`.
