#!/bin/bash

# Exit immediately if any command fails
set -e

CONTAINER_NAME="bifrost_deploy"

echo "=====> Launching OpenStack Bifrost Deployment <====="

# Change directory and execute playbooks inside the container
docker exec -it "$CONTAINER_NAME" bash -c "
    export ANSIBLE_FORCE_COLOR=true
    
    cd /bifrost/playbooks/ || { echo 'Directory not found!'; exit 1; }
    
    echo '1/2: Enrolling nodes...'
    ansible-playbook -i inventory/bifrost_inventory.py -i inventory/localhost enroll-dynamic.yaml
    sleep 10
    echo '2/2: Deploying nodes...'
    ansible-playbook -i inventory/bifrost_inventory.py -i inventory/localhost deploy-dynamic.yaml
"

echo "=====> Deployment Completed Successfully! <====="
