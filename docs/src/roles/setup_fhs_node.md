# FHS Node Setup

This role prepares and configures a node for a Kubernetes cluster. It handles the end-to-end installation process, including system prerequisites, the container runtime (`containerd`), and the core Kubernetes components (`kubeadm`, `kubelet`, and `kubectl`). It also facilitates cluster joining by provisioning the necessary `kubeadm` configuration files.

## Requirements

The role requires a Linux-based system with a functional package manager (e.g., APT) and administrative (`sudo`) privileges.

## Variables

### 1. Kubernetes Versioning
These variables control the specific versions of the Kubernetes repository and packages to be installed.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `k8s_repo_version` | `"v1.31"` | The version tag used for the Kubernetes package repository. |
| `k8s_pkg_version` | `"1.31.4"` | The specific patch version of the Kubernetes packages to install. |

### 2. Package Management
These variables define which Kubernetes binaries are installed on the host.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `k8s_packages` | `[kubelet, kubeadm, kubectl]` | A list of Kubernetes packages to be installed via the system package manager. |

### 3. Cluster Configuration
These variables manage how the node is configured within the cluster environment.

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `k8s_taints` | `[]` | A list of taints to apply to the node to control pod scheduling. |

## Execution Tags

This role utilizes Ansible tags to allow for granular control over the installation process. You can run specific components of the setup using the `--tags` flag.

| Tag | Description |
| :--- | :--- |
| `cleanup` | Triggers the removal of previous Kubernetes installations (run with `never` unless specified). |
| `prereq` | Configures system-level prerequisites. |
| `containerd` | Installs and configures the `containerd` container runtime. |
| `install-k8s` | Installs the core Kubernetes packages and manages the join configuration. |
| `join-config` | Specifically manages the creation of the `kubeadm` directory and the join configuration template. |

## License

BSD-3-Clause