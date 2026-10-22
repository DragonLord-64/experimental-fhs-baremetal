# setup_fhs_node

Installs Kubernetes dependencies and prepares a node for joining a cluster. It does not establish a completed cluster join.

## Variables

| Variable | Default | Purpose |
|---|---|---|
| `k8s_repo_version` | `v1.31` | Package repository version |
| `k8s_pkg_version` | `1.31.4` | Kubernetes package version |
| `k8s_packages` | `[kubelet, kubeadm, kubectl]` | Packages to install |
| `k8s_taints` | `[]` | Declared taints |

See `tasks/main.yml` and imported tasks for swap, kernel, containerd and Kubernetes setup. These defaults are separate from the dragonvm minikube version.

## Command and tags

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags setup_fhs_node
```

Targets `fhs_nodes`. Run from `/provision` with an explicitly reviewed inventory; this changes the target OS. The site wrapper provides the exact role tag.
