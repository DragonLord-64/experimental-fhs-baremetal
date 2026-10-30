# Managed account environment fixture

Disposable Docker test only. Uses a tiny synthetic SDK `.deb`, not BittWare's
SDK or physical cards. No controller/VM host users are changed.

On dragonvm, stage this fixture and current `roles/manage_users` under
`/home/dragon-lord/fhs-user-environments-20261030/`. Its Docker inventory targets
only the container `fhs-user-environments-20261030`.

```sh
# Controller has community.docker and ansible.posix collections.
ANSIBLE_ROLES_PATH=$PWD/roles ansible-playbook \
  -i fixture/inventory.yml fixture/converge.yml -e @fixture/vars.yml
# Verify first installation inside the container:
docker exec fhs-user-environments-20261030 python3 /tmp/verify.py 1
# Converge again; installer count must remain one.
# Upgrade fixture package via -e fpga_bittware_sdk_deb=...1.1.deb;
# verify expected installer count becomes two.
```

The fixture checks activation and `BWSDK_ROOT` during installation, all personal
venvs, shared ownership/mode, package consistency, executable entry point,
existing supplementary groups and runner isolation. Public keys and package
files are generated in the private remote workspace; do not commit private keys.
