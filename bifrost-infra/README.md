Since you requested a change to the link structure (e.g., `../docs/src/bifrost-infra/operations.md`), I have updated the paths. I have also removed all non-ASCII symbols (emojis and special characters) to ensure compatibility with all terminal emulators and text editors.

***

# bifrost-infra

Containerized OpenStack Bifrost environment for bare-metal provisioning of FHS nodes. 

Bifrost wraps Ironic with Ansible playbooks, allowing you to enrol, deploy, and manage physical servers without the overhead of a full OpenStack control plane.

---

## Quick Start

If you want to get a working environment running immediately, use the automated script:

```bash
./scripts/deploy-bifrost-container.sh
```

For a manual setup or to understand the underlying Docker/Ansible architecture, please refer to the [Quickstart Guide](../docs/src/bifrost-infra/QUICKSTART.md).

---

## Directory Structure

```text
bifrost-infra/
├── Dockerfile              # Extends Kolla Bifrost with DIB and system tools
├── docker-compose.yml      # Service definition (uses .env for host paths)
├── .env / .env.example     # Machine-local path resolution
├── image-config/           # DIB image specs and LVM partition layouts
├── dib-elements/          # Custom Diskimage-Builder elements
├── inventory/              # Ansible inventory and group variables
│   ├── group_vars/         # Configuration for localhost, baremetal, and target
│   └── *.yaml             # Per-node hardware definitions
└── scripts/                # Automation and testing utilities
```

---

## Documentation

Depending on your current task, please consult the appropriate guide:

| If you want to... | Use this guide |
| :--- | :--- |
| Manage real hardware, edit inventory, or update OS images | [Operations Guide](../docs/src/bifrost-infra/operations.md) |
| Recover from a crash or a lost Ironic database | [Recovery Guide](../docs/src/bifrost-infra/recovery.md) |
| Run a standard test cycle using libvirt VMs | [Testing Guide](../docs/src/bifrost-infra/testing.md) |

---

## Architecture Overview

### Docker Engine
The environment runs in a privileged Docker container. It utilizes network_mode: host to allow dnsmasq to provide DHCP/TFTP services to the local network and provides direct access to /dev for disk provisioning.

### Path Resolution
Because the Docker daemon resolves bind-mount paths from the host filesystem, absolute paths must be defined in a .env file (see the Quickstart Guide above for details).

### Inventory Logic
The environment uses a hybrid inventory approach:
1. Static Vars: Global defaults are stored in inventory/group_vars/baremetal.
2. Dynamic Inventory: Hardware definitions are loaded from YAML files via a custom Python script (inventory/bifrost_inventory.py).

---

## Safety Warning

AUTOMATIC CLEANING: By default, Ironic is configured to clean (wipe) nodes upon enrollment. If you are enrolling existing hardware that contains data, ensure you have configured cleaning: false in your target group variables as described in the [Operations Guide](../docs/src/bifrost-infra/operations.md).
