# setup_fhs_node

Prepares Ubuntu 24.04 for later Kubernetes registration. Never runs `kubeadm join`.
The generated `/etc/kubernetes/kubeadm/kubeadm-join.yaml` contains registration
settings only; add reviewed discovery credentials separately before a manual join.

| Variable | Default | Purpose |
|---|---|---|
| `k8s_repo_version` | `v1.31` | Kubernetes package repository minor |
| `k8s_pkg_version` | `1.31.4` | Kubernetes package patch |
| `k8s_control_plane_version` | required | Reviewed target cluster version |
| `containerd_pkg_version` | required | Exact Docker `containerd.io` package version, 1.7 or 2.x |
| `k8s_labels` | `{}` | Node registration labels |
| `k8s_taints` | `[]` | Registration taints (key, optional value, effect) |
| `k8s_enable_ceph` | `false` | Install Ceph client packages/load rbd and ceph modules |

Preflight requires matching package/repository/control-plane minors and Kubernetes
1.31 or newer for kubeadm v1beta4. This conservative same-minor policy does not
implement rolling cluster upgrades. Kubernetes 1.38+ requires containerd 2.x.
The old Kubernetes default is retained for source alignment, not automatically
upgraded or approved for a new production cluster. Set all versions deliberately;
package availability and target runtime compatibility require user review. See
[Kubernetes runtime guidance](https://kubernetes.io/docs/setup/production-environment/container-runtimes/).

Disables swap, loads networking modules, configures sysctl, installs the pinned
runtime and Kubernetes packages, and holds Kubernetes packages. APT/hold errors
fail the run. containerd defaults are generated then copied once with
`SystemdCgroup = true`; unchanged content does not rewrite or restart the service.
The role owns the complete containerd config. Ceph is optional, not a prerequisite
for every node. Affinity/tolerations belong to workloads.

```bash
ansible-playbook -i inventory/dev_env/netbox-inv.yml playbooks/site.yml --limit <HOST> --tags setup_fhs_node
```

Targets `fhs_nodes`; ensure the inventory supplies that group. Cleanup resets and
removes Kubernetes state only with an explicit `cleanup` tag; `never` alone or
role-tag inheritance cannot enable it. No host reboot is performed.

Offline fixtures cover preflight, actual registration/config rendering and
unchanged containerd writes. Kernel modules, runtime startup, package availability
and joining remain unvalidated on an isolated VM. No FPGA/hardware claims.
