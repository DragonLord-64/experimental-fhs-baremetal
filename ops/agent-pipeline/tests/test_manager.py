"""Manager dispatch preserves paused work and launches only one queued task."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HOME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOME))
import manager


class ManagerTest(unittest.TestCase):
    def test_fifo_dispatch_is_single_launch(self):
        tasks = [dict(task='newer', status='queued', created=2),
                 dict(task='older', status='queued', created=1),
                 dict(task='done', status='done', created=0)]
        with patch.object(manager.pipeline, 'scout', return_value=tasks), \
                patch.object(manager.pipeline, 'task_dir', side_effect=lambda task: HOME / task), \
                patch.object(manager.pipeline, 'launch') as launch, \
                patch.object(sys, 'argv', ['manager.py', 'dispatch-next']):
            manager.main()
        launch.assert_called_once_with(HOME / 'older')

    def test_idle_manager_does_not_resume_paused_or_blocked_work(self):
        tasks = [dict(task='paused', status='paused', created=1),
                 dict(task='blocked', status='blocked', created=0)]
        with patch.object(manager.pipeline, 'scout', return_value=tasks), \
                patch.object(manager.pipeline, 'launch') as launch, \
                patch.object(sys, 'argv', ['manager.py', 'dispatch-next']):
            manager.main()
        launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
