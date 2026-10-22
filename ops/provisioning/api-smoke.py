"""Run inside the restricted container. No conductor or hardware drivers start."""
import json
from pathlib import Path
import subprocess
import time
import urllib.request

config = Path('/tmp/ironic-prep.conf')
config.write_text('[DEFAULT]\nauth_strategy=noauth\n[database]\n'
                  'connection=sqlite:////tmp/ironic-prep.sqlite\n[api]\n'
                  'host_ip=127.0.0.1\nport=6385\napi_workers=1\n[oslo_concurrency]\nlock_path=/tmp\n')
binary = '/var/lib/kolla/venv/bin/'
subprocess.run([binary + 'ironic-dbsync', '--config-file', str(config), 'create_schema'],
               check=True, timeout=45)
with open('/tmp/ironic-api.log', 'w') as log:
    api = subprocess.Popen([binary + 'ironic-api', '--config-file', str(config)],
                           stdout=log, stderr=log)
    try:
        for attempt in range(40):
            if api.poll() is not None:
                raise RuntimeError('Ironic API exited: ' + str(api.returncode))
            try:
                with urllib.request.urlopen('http://127.0.0.1:6385/v1/nodes', timeout=1) as response:
                    assert response.status == 200
                    assert json.load(response)['nodes'] == []
                    print('Ironic API HTTP 200; empty node list verified', flush=True)
                    break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError('Ironic API readiness timeout')
    finally:
        api.terminate()
        try:
            api.wait(timeout=10)
        except subprocess.TimeoutExpired:
            api.kill()
            api.wait()
        print(Path('/tmp/ironic-api.log').read_text()[-3000:])
