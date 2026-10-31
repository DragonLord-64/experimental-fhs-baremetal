# setup_platform_ca

Install public internal CA certificates into the managed server's system trust
store before configuring HTTPS clients. No certificate or private key is generated.

Set the controller-side certificate source in inventory group vars:

```yaml
platform_ca_certificates:
  - src: "{{ fhs_resources_dir }}/certificates/platform-ca.crt"
    name: platform-ca
```

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags setup_platform_ca
```

Use one public PEM CA certificate per entry. Names use letters, numbers, `_` or
`-`; files are installed as `/usr/local/share/ca-certificates/<name>.crt` and
`update-ca-certificates` refreshes trust when they change. An empty list does
nothing. Keep private keys outside the repository and target trust store.

This role runs on targets. Install the CA on the provisioning host/container
[before loading NetBox inventory](https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal/-/blob/development2/inventory/README.md#trust-netbox-before-loading-inventory).
