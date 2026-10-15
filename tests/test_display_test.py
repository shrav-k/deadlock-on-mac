import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import unittest

from deadlock_mac import display_test
from deadlock_mac.storage import ManagerError


class DisplayRunnerTests(unittest.TestCase):
    def test_grid_survives_startup_until_cancel_and_streams_ready_before_exit(self):
        stopped = threading.Event()
        with tempfile.TemporaryDirectory() as root:
            worker = Path(root) / 'worker.py'
            worker.write_text('''import sys
print('test_window=1,2,3,4 client=2x2 buffer=2x2', flush=True)
assert sys.stdin.read() == ''
print('test_window_closed=yes result=0 reason=parent_closed', flush=True)
''')
            output = []
            def report(line):
                output.append(line)
                if line.startswith('test_window='):
                    self.assertFalse(stopped.is_set())
                    stopped.set()
            result = display_test.run([sys.executable, str(worker)], env=os.environ.copy(), cwd=root,
                                      stopped=stopped, report=report)
            self.assertEqual(result.returncode, 0)
            self.assertIn('reason=parent_closed', result.stdout)
            self.assertIn('Closing the owned test grid…', output)

    def test_normal_user_close_needs_no_cancel(self):
        result = display_test.run([sys.executable, '-c', "print('test_window_closed=yes result=0 reason=escape')"],
                                  env=os.environ.copy(), cwd='.', stopped=threading.Event(), report=lambda _: None)
        self.assertEqual(result.returncode, 0)
        self.assertIn('reason=escape', result.stdout)

    def test_signal_is_a_close_request_and_previous_handlers_are_restored(self):
        before = signal.getsignal(signal.SIGTERM)
        with display_test.cancellation() as stopped:
            signal.raise_signal(signal.SIGTERM)
            self.assertTrue(stopped.is_set())
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)

    def test_cancellation_before_spawn_starts_no_helper(self):
        stopped = threading.Event(); stopped.set()
        with self.assertRaisesRegex(ManagerError, 'before startup'):
            display_test.run(['/does/not/exist'], env={}, cwd='.', stopped=stopped)
