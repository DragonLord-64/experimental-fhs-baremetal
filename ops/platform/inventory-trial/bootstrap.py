#!/usr/bin/env python3
"""Create the private v1 trial token without placing it in process arguments."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
credentials = json.loads((root / 'credentials.json').read_text())
code = '''
from users.models import Token, User
from users.choices import TokenVersionChoices
from netbox.config import get_config
import json
credentials = json.loads(CREDENTIALS)
Token.objects.get_or_create(
    user=User.objects.get(username=credentials['username']),
    version=TokenVersionChoices.V1, description='Synthetic inventory trial', defaults={
    'token': credentials['token'],
    'write_enabled': True,
})
print('TRIAL_METADATA=' + json.dumps({'changelog_retention_days': get_config().CHANGELOG_RETENTION}))
'''.replace('CREDENTIALS', repr(json.dumps(credentials)))
result = subprocess.run([
    'docker', 'compose', 'exec', '-T', 'netbox', '/opt/netbox/venv/bin/python',
    '/opt/netbox/netbox/manage.py', 'shell', '--no-startup', '--no-imports',
    '--interface', 'python',
], cwd=root, input=code, text=True, capture_output=True)
if result.returncode:
    diagnostic = result.stdout + result.stderr
    for value in credentials.values():
        diagnostic = diagnostic.replace(value, '<redacted>')
    raise SystemExit('Token bootstrap failed:\n' + diagnostic[-4000:])
metadata = next(line.removeprefix('TRIAL_METADATA=') for line in result.stdout.splitlines()
                if line.startswith('TRIAL_METADATA='))
(root / 'metadata.json').write_text(metadata + '\n')
print('Trial token ready; change-log retention days:', json.loads(metadata)['changelog_retention_days'])
