import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'pipeline.py'
spec = importlib.util.spec_from_file_location('pipeline', SOURCE)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.home = self.repo / 'ops/agent-pipeline'
        self.home.mkdir(parents=True)
        self.script = self.home / 'pipeline.py'
        shutil.copy(SOURCE, self.script)
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'base'], check=True)
        self.fake = self.repo / 'fake-codex'
        self.fake.write_text('''#!/usr/bin/env python3
import json, pathlib, sys, time
prompt = sys.stdin.read()
stage = prompt.split('STAGE: ')[1].splitlines()[0]
print(json.dumps({'type': 'thread.started', 'thread_id': 'fake-' + stage}), flush=True)
root = pathlib.Path(__file__).parent
if (root / 'slow').exists(): time.sleep(30)
status = 'passed' if stage == 'review' else 'ready'
if stage == 'review' and (root / 'reject').exists(): status = 'changes_required'
if (root / 'bad').exists(): status = 'passed'
out = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])
out.write_text(json.dumps(dict(status=status, summary=stage, handoff='useful context', evidence=['observed fake test'])))
''')
        self.fake.chmod(0o755)
        self.task = self.repo / 'task.txt'
        self.task.write_text('Test literal $(touch PWNED) `touch PWNED2` ; spaces')
        self.config = self.repo / 'config.json'
        self.settings = dict(codex=str(self.fake), timeout=10, max_runs=8,
                             max_retries=1, checks=[['python3', '-c', 'print("verified")']])

    def cli(self, *args):
        result = subprocess.run(['python3', str(self.script), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def start(self):
        self.config.write_text(json.dumps(self.settings))
        self.id = self.cli('start', '--task-file', str(self.task), '--config', str(self.config)).strip()
        self.run = self.home / 'runs' / self.id
        self.addCleanup(self.cleanup_worker)

    def cleanup_worker(self):
        state = json.loads((self.run / 'state.json').read_text())
        for key in ('agent_pid', 'worker_pid'):
            if state.get(key):
                try: os.kill(state[key], 15)
                except ProcessLookupError: pass

    def wait(self, predicate, seconds=10):
        deadline = time.time() + seconds
        while time.time() < deadline:
            state = json.loads((self.run / 'state.json').read_text())
            if predicate(state): return state
            time.sleep(.05)
        self.fail('Timed out: ' + str(state))

    def test_happy_path_fresh_runs_and_literal_task(self):
        self.start()
        state = self.wait(lambda s: s['status'] in pipeline.TERMINAL)
        self.assertEqual(state['status'], 'done', state)
        self.assertEqual(state['attempt'], 1)
        self.assertTrue(state['review_required'])
        self.assertEqual(state['stage'], 'implement')
        self.assertIn('verified', (self.run / 'verification.log').read_text())
        self.assertEqual(len(list(self.run.glob('*.prompt.txt'))), 1)
        self.assertFalse((self.repo / 'PWNED').exists())
        self.assertFalse((self.repo / 'PWNED2').exists())

    def test_no_review_worker_or_review_retry_gate(self):
        (self.repo / 'reject').touch()
        self.start()
        state = self.wait(lambda s: s['status'] in pipeline.TERMINAL)
        self.assertEqual(state['status'], 'done', state)
        self.assertEqual(state['attempt'], 1)
        self.assertFalse(list(self.run.glob('*-review.*')))
        self.assertIn('user review pending', state['reason'])

    def test_legacy_review_checkpoint_resumes_implementation(self):
        (self.repo / 'slow').touch()
        self.start()
        self.wait(lambda s: s.get('agent_thread'))
        self.cli('pause', self.id)
        state = self.wait(lambda s: s['status'] == 'paused')
        # Stop this owned worker, preserving the checkpoint, to emulate an upgrade.
        os.kill(state['worker_pid'], signal.SIGTERM)
        self.wait(lambda s: s['status'] == 'blocked')
        state = json.loads((self.run / 'state.json').read_text())
        state.update(status='paused', stage='review', handoff={'summary':'legacy findings'})
        (self.run / 'state.json').write_text(json.dumps(state))
        (self.repo / 'slow').unlink()
        self.cli('resume', self.id)
        self.cli('_run', self.id)
        state = self.wait(lambda s: s['status'] in pipeline.TERMINAL)
        self.assertEqual(state['status'], 'done', state)
        self.assertEqual(state['stage'], 'implement')
        self.assertEqual(state['attempt'], 2)
        self.assertFalse(list(self.run.glob('*-review.prompt.txt')))

    def test_invalid_transition(self):
        (self.repo / 'bad').touch()
        self.start()
        state = self.wait(lambda s: s['status'] == 'blocked')
        self.assertIn('Invalid stage transition', state['reason'])

    def test_failed_controller_checks_cannot_pass(self):
        self.settings['checks'] = [['python3', '-c', 'raise SystemExit(2)']]
        self.start()
        state = self.wait(lambda s: s['status'] in pipeline.TERMINAL)
        self.assertEqual(state['status'], 'blocked')
        self.assertIn('verification failed', state['reason'])

    def test_pause_redirect_resume_cancel(self):
        (self.repo / 'slow').touch()
        self.start()
        first = self.wait(lambda s: s.get('agent_thread'))
        self.cli('pause', self.id)
        self.wait(lambda s: s['status'] == 'paused')
        self.cli('redirect', self.id, 'Keep the original goal; add this correction')
        self.wait(lambda s: s.get('corrections'))
        self.cli('resume', self.id)
        second = self.wait(lambda s: s.get('agent_pid') and s['attempt'] == 2)
        self.assertNotEqual(first['agent_pid'], second['agent_pid'])
        self.assertIn('correction', Path(second['log'].replace('.events.jsonl', '.prompt.txt')).read_text())
        self.cli('cancel', self.id)
        self.wait(lambda s: s['status'] == 'cancelled')
        self.assertTrue(list(self.run.glob('interrupted-*.patch')))

    def test_timeout(self):
        (self.repo / 'slow').touch()
        self.settings['timeout'] = 1
        self.start()
        state = self.wait(lambda s: s['status'] == 'blocked')
        self.assertIn('timeout', state['reason'])

    def test_cancel_during_controller_verification(self):
        self.settings['checks'] = [['python3', '-c', 'import time; time.sleep(30)']]
        self.start()
        deadline = time.time() + 10
        while not (self.run / 'verification.log').exists() and time.time() < deadline:
            time.sleep(.05)
        self.assertTrue((self.run / 'verification.log').exists())
        state = self.wait(lambda s: s.get('phase') == 'verification')
        self.assertTrue(state['verification_pid'])
        self.assertEqual(state['check_index'], 1)
        self.assertTrue(state['log'].endswith('verification.log'))
        self.assertEqual(state['check_argv'], self.settings['checks'][0])
        self.cli('cancel', self.id)
        self.wait(lambda s: s['status'] == 'cancelled')

    def test_cancel_is_terminal_with_queued_redirect(self):
        (self.repo / 'slow').touch()
        self.start()
        state = self.wait(lambda s: s.get('agent_pid'))
        # Stop the controller briefly to deterministically queue one batch.
        os.kill(state['worker_pid'], signal.SIGSTOP)
        try:
            self.cli('cancel', self.id)
            self.cli('redirect', self.id, 'Must not restart a cancelled task')
        finally:
            os.kill(state['worker_pid'], signal.SIGCONT)
        final = self.wait(lambda s: s['status'] == 'cancelled')
        self.assertEqual(final['attempt'], 1)

    def test_duplicate_worker_does_not_change_active_state(self):
        (self.repo / 'slow').touch()
        self.start()
        before = self.wait(lambda s: s.get('agent_pid'))
        self.cli('_run', self.id)
        after = json.loads((self.run / 'state.json').read_text())
        self.assertEqual(after['status'], 'running')
        self.assertEqual(after['agent_pid'], before['agent_pid'])
        self.cli('cancel', self.id)
        self.wait(lambda s: s['status'] == 'cancelled')

    def test_repository_lock(self):
        (self.repo / 'slow').touch()
        self.start()
        self.wait(lambda s: s.get('agent_pid'))
        first_id, first_run = self.id, self.run
        result = subprocess.run(['python3', str(self.script), 'start', '--task-file', str(self.task),
                                 '--config', str(self.config)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('running/paused work', result.stderr)
        self.cli('cancel', first_id)
        self.id, self.run = first_id, first_run
        self.wait(lambda s: s['status'] == 'cancelled')

    def test_intake_scout_dispatch(self):
        self.config.write_text(json.dumps(self.settings))
        self.id = self.cli('intake', '--task-file', str(self.task), '--config', str(self.config)).strip()
        self.run = self.home / 'runs' / self.id
        self.addCleanup(self.cleanup_worker)
        tasks = json.loads(self.cli('scout'))
        self.assertEqual(tasks[0]['status'], 'queued')
        self.assertFalse(tasks[0]['controller_alive'])
        self.assertFalse(list(self.run.glob('*.prompt.txt')))
        self.cli('dispatch', self.id)
        state = self.wait(lambda s: s['status'] in pipeline.TERMINAL)
        self.assertEqual(state['status'], 'done')
        prompt = next(self.run.glob('*.prompt.txt')).read_text()
        self.assertIn('Do not run those commands yourself', prompt)
        self.assertIn('120 seconds per command', prompt)

    def test_duplicate_checks_rejected(self):
        self.settings['checks'] *= 2
        self.config.write_text(json.dumps(self.settings))
        result = subprocess.run(['python3', str(self.script), 'intake', '--task-file', str(self.task),
                                 '--config', str(self.config)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Duplicate verification', result.stderr)

    def test_queued_cancel_does_not_launch_worker(self):
        self.config.write_text(json.dumps(self.settings))
        self.id = self.cli('intake', '--task-file', str(self.task), '--config', str(self.config)).strip()
        self.run = self.home / 'runs' / self.id
        self.cli('cancel', self.id)
        state = json.loads((self.run / 'state.json').read_text())
        self.assertEqual(state['status'], 'cancelled')
        self.assertFalse(list(self.run.glob('*.prompt.txt')))

    def test_check_timeout_is_separate_from_worker_budget(self):
        self.settings.update(check_timeout=1, checks=[['python3', '-c', 'import time; time.sleep(30)']])
        self.start()
        state = self.wait(lambda s: s['status'] == 'blocked')
        self.assertIn('verification timeout', state['reason'])

    def test_result_validation(self):
        for result in ({}, {'status': 'ready', 'summary': '', 'handoff': '', 'evidence': []}):
            with self.assertRaises(ValueError): pipeline.validate_result(result, 'screen')


if __name__ == '__main__':
    unittest.main()
