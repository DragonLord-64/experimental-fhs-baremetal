"""Exercise isolated deliverable copies and relocated lab entrypoints, without services."""
import json
import base64
import gzip
import hashlib
import os
from pathlib import Path
import shutil
import re
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
SHARED = ('platform', 'playbooks', 'roles', 'inventory', 'docs', 'scripts', 'testing', 'bifrost-infra')


class SourceBoundaryTest(unittest.TestCase):
    def test_shared_runtime_does_not_depend_on_lab_trees(self):
        for folder in SHARED:
            for path in (ROOT / folder).rglob('*'):
                if path.is_symlink():
                    self.assertTrue(path.resolve().is_relative_to(ROOT / folder), str(path))
                    self.assertTrue(path.resolve().exists(), str(path))
                elif path.suffix in ('.py', '.sh', '.yml', '.yaml', '.cfg') and path.is_file():
                    text = path.read_text()
                    for private in ('ops/', 'wiki/', 'examples/', 'tests/molecule', 'grafana_dashboards'):
                        self.assertNotIn(private, text, str(path))

    def test_shared_local_document_links_do_not_require_lab_trees(self):
        for folder in SHARED:
            for path in (ROOT / folder).rglob('*.md'):
                for target in re.findall(r'\]\(([^\s)]+)\)', path.read_text()):
                    if re.match(r'\w+:|/|#|\$|<', target): continue
                    resolved = (path.parent / target.split('#')[0]).resolve()
                    for private in ('ops', 'wiki', 'examples'):
                        self.assertFalse(resolved.is_relative_to(ROOT / private), (str(path), target))

    def test_recorded_capture_and_official_source_bytes_are_preserved(self):
        manifest = json.loads((ROOT / 'ops/source-boundary/PROVENANCE.json').read_text())
        files = dict(manifest['preserved_official_files'])
        files.update({item['after']: item['sha256'] for item in manifest['moved_immutable_files']})
        for name, expected in files.items():
            self.assertEqual(expected, hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), name)

    def test_lab_material_is_outside_shared_sources(self):
        for path in ('platform/grafana_dashboards', 'platform/example_output', 'docs/test-environment-plan.md', 'scripts/test-manage-users.sh'):
            self.assertFalse((ROOT / path).exists(), path)
        for path in ('ops/dashboards/generated/rack.json', 'ops/telemetry/captures/fhs-prometheus-sample.json',
                     'wiki/test-environment-plan.md', 'ops/role-tests/manage_users/molecule/default/create.yml'):
            self.assertTrue((ROOT / path).is_file(), path)

    def test_copied_platform_renders_and_build_context_is_local(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'platform', root / 'platform', symlinks=True)
            result = subprocess.run(['helm', 'template', 'copy-check', str(root / 'platform/charts/fhs-platform'),
                                     '--namespace', 'copy-check'], capture_output=True, text=True, check=True)
            objects = [item for item in yaml.safe_load_all(result.stdout) if item]
            self.assertTrue(any(item['kind'] == 'Deployment' and item['metadata']['name'] == 'fhs-netbox' for item in objects))
            archives = next(item['binaryData'] for item in objects if item['kind'] == 'ConfigMap' and item['metadata']['name'] == 'fhs-dashboard-archives')
            self.assertEqual(6, len(archives))
            for data in archives.values():
                self.assertTrue(json.loads(gzip.decompress(base64.b64decode(data)))['uid'])
            binary = root / 'fake-bin'; binary.mkdir()
            capture = root / 'build-args.json'
            (binary / 'docker').write_text('#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["BUILD_CAPTURE"]).write_text(json.dumps(sys.argv[1:]))\n')
            (binary / 'docker').chmod(0o755)
            subprocess.run(['bash', str(root / 'platform/netbox-image/build.sh')], check=True,
                           env=dict(os.environ, PATH=str(binary)+os.pathsep+os.environ['PATH'], BUILD_CAPTURE=str(capture)),
                           cwd=root, capture_output=True, text=True)
            args = json.loads(capture.read_text()); context = Path(args[-1])
            self.assertTrue(context.resolve().is_relative_to(root / 'platform'))
            self.assertTrue((context / 'Dockerfile').is_file())
            self.assertIn('netbox-inventory==2.7.1', (context / 'Dockerfile').read_text())

    def test_moved_role_runner_selects_lab_project_and_shared_role(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'ops/role-tests', root / 'ops/role-tests')
            shutil.copytree(ROOT / 'roles/manage_users', root / 'roles/manage_users')
            binary = root / 'fake-bin'; binary.mkdir(); capture = root / 'molecule-cwd.txt'
            programs = {
                'git': '#!/bin/sh\necho synthetic-commit\n',
                'ansible': '#!/bin/sh\necho synthetic-ansible\n',
                'docker': '#!/bin/sh\nif [ "$1" = inspect ]; then exit 1; fi\nexit 0\n',
                'molecule': '#!/bin/sh\nif [ "$1" = --version ]; then echo synthetic-molecule; else pwd > "$RUNNER_CAPTURE"; test -f molecule/default/create.yml; fi\n',
            }
            for name, text in programs.items():
                (binary / name).write_text(text); (binary / name).chmod(0o755)
            subprocess.run(['bash', str(root / 'ops/role-tests/manage_users/run.sh')], cwd=root, check=True,
                           env=dict(os.environ, PATH=str(binary)+os.pathsep+os.environ['PATH'], RUNNER_CAPTURE=str(capture)),
                           capture_output=True, text=True)
            project = root / 'ops/role-tests/manage_users'
            self.assertEqual(project, Path(capture.read_text().strip()))
            config = yaml.safe_load((project / 'molecule/default/molecule.yml').read_text())
            roles = config['provisioner']['env']['ANSIBLE_ROLES_PATH'].replace('${MOLECULE_PROJECT_DIRECTORY}', str(project))
            self.assertTrue((Path(roles) / 'manage_users/tasks/main.yml').is_file())
            reports = list((root / 'build/reports/molecule').glob('*/cleanup.log'))
            self.assertEqual(1, len(reports)); self.assertIn('exit=0', reports[0].read_text())


if __name__ == '__main__': unittest.main()
