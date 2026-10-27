

The `bifrost-infra/` container uses host networking and privilege. Review the target network before running it. Bifrost playbooks are supplied by the image under `/opt/bifrost/playbooks`.


# Quickstart Guide

Follow these steps to get a containerized Bifrost environment running and perform your first deployment.

## Prerequisites
* Docker and Docker Compose installed.
* Access to `sudo` (required for network binding and privileged mode).
* A valid SSH public key at `~/.ssh/id_rsa.pub` (used for injecting credentials into new nodes).

## 1. Automated Setup (Recommended)
If you want to skip manual configuration and just test the environment, use the provided automation script.

```bash
# This script configures the environment, builds the container, and starts services
./scripts/deploy-bifrost-container.sh
```
Enter password into .vault_pass

```bash
echo "<password>" > .vault_pass
```

## 2. Manual Setup
If you prefer to control the configuration manually:

### A. Configure Environment
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env to set absolute paths for your local machine
# Example: BIFROST_DIR=/home/user/bifrost-infra
vi .env

# Create the Vault password file (required by Ansible)
touch ../.vault_pass && chmod 600 ../.vault_pass
sudo echo "<password>" > .vault_pass
```

### B. Build and Start
```bash
# Build the custom Bifrost image
sudo docker compose build

# Start the services in the background
sudo docker compose up -d
```

### C. Initialize the Services
Once the container is running, you must run the installation playbook to set up Ironic, DNS, and HTTP services.

```bash
# Enter the container
sudo docker exec -it bifrost_deploy bash

# Inside the container, run the install playbook
cd /bifrost/playbooks
ansible-playbook -i inventory/target install.yaml
```

## 3. Verify the Installation
To ensure the services are healthy, check the status of the Ironic nodes:

```bash
# Check if the Ironic API is responding
baremetal node list
```

---


## 4. Update Bifrost Inventory
Update the bifrost inventory variables in the conatiner.

```bash
vi /bifrost/playbooks/inventory/terabox1501b_inventory.yaml
```

## 5. Enroll and Deploy
Enroll and clean the nodes
```text
this will wipe the harddrives of the nodes
```
```bash
cd /bifrost/playbooks
ansible-playbook -i inventory/bifrost_inventory.py -i inventory/localhost enroll-dynamic.yaml
```
Install the operating system
```bash
cd /bifrost/playbooks
ansible-playbook -i inventory/bifrost_inventory.py -i inventory/localhost deploy-dynamic.yaml
```

## 6. Verify 
Display the status of all nodes.

```bash
baremetal node list
```

## Details
See **[Operations Guide](operations.md)** for more information on these processes.


