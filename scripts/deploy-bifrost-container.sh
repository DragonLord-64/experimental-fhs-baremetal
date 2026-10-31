#!/usr/bin/env bash

# Exit immediately if any command fails
set -e

echo "--> Navigating to infrastructure directory..."
cd bifrost-infra

echo "--> Ensuring Ansible Vault password file exists with secure permissions..."
touch ../.vault_pass
sudo chmod 660 ../.vault_pass

echo "--> Rebuilding and starting Bifrost containers..."
docker compose build
docker compose up -d

echo "--> Waiting for container services to initialize..."
sleep 2 

echo "--> Installing Ansible roles from requirements.yml..."
docker exec -w /provision bifrost_deploy ansible-galaxy role install -r requirements.yml -p ./roles/

echo "--> Running Bifrost Install playbook..."
docker exec -w /bifrost/playbooks bifrost_deploy python3 /provision/scripts/patch-bifrost-environment.py configure --build-images

# Drop into the container only if running in an interactive terminal (human user)
if [ -t 0 ]; then
    echo "--> Dropping into container shell..."
    docker exec -it bifrost_deploy bash
else
    echo "--> Non-interactive environment detected. Skipping shell access."
fi
