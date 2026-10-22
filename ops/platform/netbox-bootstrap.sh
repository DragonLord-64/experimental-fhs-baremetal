#!/usr/bin/env bash
# NetBox v4.7 no longer bootstraps legacy api_token-only chart secrets.
# Create the lab token inside the pod; never transfer it through argv or output.
set -euo pipefail
minikube -p fhs-test kubectl -- --context=fhs-test -n fhs-platform exec -i deploy/netbox -- \
  /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py shell --no-startup --no-imports --interface python <<'PY'
from pathlib import Path
from users.models import Token, User
import os
user = User.objects.get(username=os.environ.get('SUPERUSER_NAME', 'admin'))
value = Path('/run/secrets/superuser_api_token').read_text().strip()
if not Token.objects.filter(user=user, description='FHS lab validation', version=1).exists():
    Token.objects.create(user=user, version=1, token=value, description='FHS lab validation', write_enabled=True)
print('Lab API authentication configured')
PY
