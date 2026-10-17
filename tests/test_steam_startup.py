import tempfile
import unittest
from pathlib import Path

from deadlock_mac.steam_startup import MAX_BYTES, failure_summary


class StartupDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve() / 'this-launch.log'

    def test_stalled_mainloop_is_not_misreported_as_display_or_login_failure(self):
        for marker in ('CSteamEngine::BMainLoop appears to have stalled > 15 seconds',
                       'fatal stalled cross-thread pipe'):
            self.path.write_text('private account data\r\n' + marker)
            message = failure_summary(self.path)
            self.assertIn('Steam reported a stalled main loop', message)
            self.assertIn('Display settings were left unchanged', message)
            self.assertNotIn('private account data', message)

    def test_missing_generic_or_linked_log_does_not_invent_a_cause(self):
        self.assertIsNone(failure_summary(self.path))
        self.path.write_text('Wine warning; Steam is updating')
        self.assertIsNone(failure_summary(self.path))
        link = self.path.with_name('link.log')
        link.symlink_to(self.path)
        self.assertIsNone(failure_summary(link))

    def test_large_log_is_bounded_and_only_recent_tail_is_used(self):
        self.path.write_bytes(b'fatal stalled cross-thread pipe\n' + b'x' * MAX_BYTES)
        self.assertIsNone(failure_summary(self.path))
        with self.path.open('ab') as stream:
            stream.write(b'\xff fatal stalled cross-thread pipe')
        self.assertIsNotNone(failure_summary(self.path))
