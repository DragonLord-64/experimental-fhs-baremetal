# ska‑mid‑cbf‑fhs‑baremetal  
**Tooling for provisioning and managing the SKA Mid‑CBF FHS bare‑metal environment**  

ReadTheDocs: https://ska-mid-cbf-fhs-baremetal.readthedocs.io/en/stable/
---  
## Installation
```bash
git submodule init
git submodule update
poetry install # to create the virtual environment with all dependencies
```
## Building ReadTheDocs
```bash
make docs-build html
```
Run `make docs-build clean` to remove old docs as required.


## Repository layout  

| Path                          | Description                                                                                                                                                                                        | Where to edit/add                                                                                                                                                                                                                 |
|-------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `bifrost-infra/`              | Dockerfile **and** the **docker‑compose** file (`docker-compose.yml`) that builds the Bifrost (Ironic) container. Bifrost settings and config files. Also where .ssh folder is mounted (gitignored | Add/change container configuration, environment variables, or mounts here. After any change, rebuild with `docker compose up -d --build`.                                                                                         |
| `inventory/`                  | Ansible inventory – hosts, groups, and `group_vars/`. This is the **single source of truth** for all nodes.                                                                                        | Add new hosts, groups, or variables; changes are reflected instantly because the directory is bind‑mounted into the container.                                                                                                    |
| `playbooks/`                  | Core post‑provisioning workspace, contains the playbooks that are used to defined tagged jobs to run.                                                                                              | Add new roles under `playbooks/roles/`.                                                                                                                                                                                           |
| `scripts/`                    | Helper shell utilities (e.g. `run-playbook.sh`).                                                                                                                                                   | Add or modify helper scripts. The scripts directory is mounted read‑only inside the container, so you can edit them locally and re‑run without rebuilding the image.                                                              |
| `docs/src`                    | Source directory that is used by the pipeline to generate the Read The Docs HTML Documentation.                                                                                                    | Add or modify Markdown files in the `/playbooks` or `/roles` directory, depending on edits.                                                                                                                                       |
| `.vault_pass` **Git-ignored** | Plain‑text file that contains the Ansible Vault password (used only for local development).                                                                                                        | **Never commit** this file. If you later enable Ansible Vault, keep the file here (or point `VAULT_PASS_FILE` at another location).                                                                                               |
| `requirements.yml`            | File that lists external collections or roles that are added as dependencies.                                                                                                                      | To add a new collection or role, update `requirements.yml` and run the appropriate ansible-galaxy command:  • `ansible-galaxy install collection -r requirements.yml -p ` • `ansible-galaxy install role -r requirements.yml -p ` |
| `.ansible-lint`               | Configuration file for the ansible-lint tool, specifying which linting rules and warnings to skip.                                                                                                 | Refer to the [ansible-lint rules](https://docs.ansible.com/projects/lint/rules/) on what rules to skip if required.                                                                                                               |
| `ansible.cfg`                 | Config file for Ansible itself. Mainly used for specifying directory paths to use.                                                                                                                 |                                                                                                                                                                                                                                   |

---  

## Getting started  

### Prerequisites  

| Tool | Minimum version | Why we need it |
|------|----------------|----------------|
| Docker Engine | 24.0+ | Runs the privileged Bifrost container. |
| Docker Compose (v2) | 2.20+ | Parses `bifrost-infra/docker-compose.yml`. |


> **Linux host required** – the Bifrost container mounts privileged devices (`/dev`, `/sys/fs/cgroup`, etc.). 

### Clone the repository  

```bash
git clone https://gitlab.com/ska-telescope/sdi/ska-mid-cbf-fhs-baremetal.git
cd ska-mid-cbf-fhs-baremetal
```

### Create a local `.env` (optional)

All paths used by Docker‑Compose can be overridden with environment variables.  
If you keep the default layout you can **skip** this file, but it’s handy when you want to work from a different root or when CI supplies its own values.

```bash
# .env  (placed in repository root)
VAULT_PASS_FILE=../.vault_pass          # path to the vault‑password file (git‑ignored)
BIFROST_DIR=./bifrost-infra/            # folder that contains docker‑compose.yml
INVENTORY_DIR=./inventory               # Specifies the inventory directory to use, containing the host file and the host variables
PLAYBOOKS_DIR=./playbooks               # Specifies the directory that contains the YAML ansible playbooks
RESOURCES_DIR=/shared/midcbf_provision_files.d
SCRIPTS_DIR=./scripts
ROLES_DIR=./roles                       # Specifies the directory to that contains the roles used by the playbooks
```

> **What happens if a variable is missing?**  
> Docker Compose falls back to the literal `${VAR}` string, which will cause the container start to fail. Keep the `.env` in version control only for documentation purposes – the real values are usually supplied by the developer’s shell or CI.

### Build & start the Bifrost container  

```bash
./scripts/deploy-bifrost-container.sh
```

The container is built from `bifrost-infra/Dockerfile` and started using the `docker-compose.yml` located **inside the same directory** (`bifrost-infra/docker-compose.yml`).  

You can verify it’s running:

```bash
docker compose ps                # shows the container status
docker compose -it exec bifrost bash # drops you into a shell inside the container
```

### Run a playbook inside container (example)  

```bash
cd /provision/playbooks
ansible-playbook -i../inventory/dev_env provision.yml"
```

## How to add or change things safely  

| What you want to change | Where to edit | What to do after editing |
|--------------------------|---------------|--------------------------|
| **Add a new host** | `inventory/dev_env/hosts.yaml` (or any host‑specific file) | also create host variables in `inventory/dev_env/host_vars/` |
| **Add a new group variable** | `inventory/group_vars/<group>.yaml` | Same – immediate effect. |
| **Create a new role** | `playbooks/roles/<my_role>/` (run `ansible-galaxy role init <my_role>`) | If the role has external Ansible‑Galaxy dependencies, add them to `requirements.yml` and run `ansible-galaxy install role -r requirements.yml -p <path to roles folder>` |
| **Add a third‑party collection** | `requirements.yml` | Inside the container, run `ansible-galaxy collection install -r requirements.yml -p <path to collections folder>` |
| **Modify the Docker image (e.g. add a system package)** | `bifrost-infra/Dockerfile` | Re‑run `docker compose up -d --build`. The `/var/lib/ironic` volume on the host is persisted, so cached images are kept. |
| **Change a mount or environment variable** | `bifrost-infra/docker-compose.yml` **or** a local `.env` | Re‑run `docker compose up -d` (no rebuild needed unless you touched the Dockerfile). |
| **Update a helper script** | `scripts/` | No container restart needed – the script directory is bind‑mounted. |
| **Add a Molecule test (NOT SETUP YET)** | | |

### Best‑practice checklist before pushing  

1. **Static analysis** – `ansible-lint` on all playbooks/roles, `shellcheck` on scripts.  
2. **Container rebuild** – if Dockerfile, compose, or mount changes were made, run `docker compose up -d --build`.  
3. **Dry‑run playbooks** – `ansible-playbook --check …` to catch syntax errors early.  
4. **Test on Hardware**

---  

## Secrets & Vault  

* The **Ansible Vault password file** (`.vault_pass`) lives at the repository root and is **git‑ignored**.  
* By default the container expects it at `/root/.vault_pass` (see the `environment:` entry in `docker-compose.yml`).  


## Testing & CI  

TBD
