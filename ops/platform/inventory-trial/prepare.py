#!/usr/bin/env python3
"""Generate isolated lab secrets once; never print their contents."""
import json
import os
from pathlib import Path
import secrets

root = Path(__file__).resolve().parent
env = root / '.env'
if env.exists():
    raise SystemExit('Existing .env preserved; preparation skipped.')
password = secrets.token_urlsafe(30)
db_password = secrets.token_urlsafe(30)
token = secrets.token_hex(20)
values = {
    'POSTGRES_DB': 'netbox', 'POSTGRES_USER': 'netbox', 'POSTGRES_PASSWORD': db_password,
    'DB_HOST': 'postgres', 'DB_NAME': 'netbox', 'DB_USER': 'netbox', 'DB_PASSWORD': db_password,
    'REDIS_HOST': 'valkey', 'REDIS_CACHE_HOST': 'valkey', 'REDIS_DATABASE': '0',
    'REDIS_CACHE_DATABASE': '1', 'SECRET_KEY': secrets.token_urlsafe(60),
    'ALLOWED_HOSTS': 'localhost 127.0.0.1', 'GRANIAN_WORKERS': '1',
    'SUPERUSER_NAME': 'trial-admin', 'SUPERUSER_EMAIL': 'trial@example.invalid',
    'SUPERUSER_PASSWORD': password, 'MAX_DB_WAIT_TIME': '120',
    'BANNER_TOP': 'SYNTHETIC DISPOSABLE INVENTORY TRIAL — no real hardware',
}
old_umask = os.umask(0o077)
try:
    env.write_text(''.join(f'{k}={v}\n' for k, v in values.items()))
    (root / 'credentials.json').write_text(json.dumps({
        'username': 'trial-admin', 'password': password, 'token': token,
        'url': 'http://127.0.0.1:18087',
    }) + '\n')
finally:
    os.umask(old_umask)
print('Created private .env and credentials.json for synthetic trial.')
