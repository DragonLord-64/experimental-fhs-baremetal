# Hardware management

Application entry point: `scripts/hwmanage/hwmanage`. Install it inside Bifrost from the
repository root:

```bash
scripts/install-hwmanage.sh
hwmanage --help
```

Edit [config.yml](config.yml) for controller paths, endpoints, inventory and import
defaults. Set existing NetBox site/role names or slugs and device-type model or slug under
`import.new_device_defaults`.
Use `hwmanage config show` or `hwmanage config validate` to inspect settings.
The provisioning interface is selected from the inspected boot MAC. These are
tracked, non-secret settings;
credentials stay in `/provision/files.d/credentials/`.

See the [operator guide](../../docs/src/playbooks/hwmanage.md) for file formats,
credential paths and commands. Native import playbooks remain in
`playbooks/netbox/`.

NetBox's product serial is the Ironic node name. The wrapper creates or updates
that name and does not require an Ironic UUID custom field in NetBox. Import
names the discovery with its verified serial; sync can find and name an existing
discovery through its provisioning port. Conflicting registrations fail for
manual cleanup; they are never automatically removed.

When the minimal import creates a temporary `provisioning` interface, the later
full interface inventory matches its MAC and renames that same NetBox interface
to the observed Linux name. Its provisioning tag, MAC and assigned addresses stay
attached. A conflicting existing interface name requires operator review.
