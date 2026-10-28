# remove_fhs_grpc

Stop/disable `fsp-grpc.service` and `vcc-grpc.service`, remove their role-owned
unit files, then remove the controller installations and Python environments.
The certificate cleanup playbook calls this role before deleting the shared FHS
and runner venvs. `site.yml` no longer installs either controller.

```sh
ansible-playbook -i inventory/dev_env/hosts.yml playbooks/development/certificate-update.yml --limit <HOST>
ansible-playbook -i inventory/dev_env/hosts.yml playbooks/site.yml --limit <HOST> --tags python_ca_updates,manage_venvs,manage_bittware_sdk,manage_gitlab-runner,audit_python_ca
```

Cleanup removes:

- `/opt/grpc/fsp`, `/opt/grpc/vcc` and `/opt/grpc/poetry`;
- legacy `/etc/grpc/fsp` and `/etc/grpc/vcc` installations;
- only `ska-mid-cbf-fhs-fsp-grpc-controller-*-py*` and
  `ska-mid-cbf-fhs-vcc-grpc-controller-*-py*` directories immediately under
  `/root/.cache/pypoetry/virtualenvs`.

Missing services/directories are accepted; a service stop failure stops cleanup.
The shared bitstreams, SDK, hardware accounts/groups, personal gRPC projects and
unrelated Poetry environments remain. Existing systemd drop-ins are not removed.
Inventory can override the four cleanup roots in `defaults/main.yml`; review
those paths before using a non-default installation layout.

The certificate playbook also updates the Ubuntu CA package, checks the decoded
system bundle for the removed emSign root, deletes `/opt/venvs/fhs` and
`/home/gitlab-runner/.bw_venv`, and refreshes Snap packages if Snap is installed.
It does not upgrade the personal gRPC project's certifi or clear the shared
virtualenv seed cache; those separate audit findings still require remediation.
