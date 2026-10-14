"""Qualification mode must never turn a Steam-only check into a game test."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location('lifecycle_harness', Path(__file__).resolve().parents[1] / 'packaging/check_lifecycle.py')
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


class SteamOnlyHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(harness, 'load_profile', return_value={'prefix': str(self.root / 'bottle')}))
        self.games = self.stack.enter_context(patch.object(harness.game_session, 'games_in_prefix', return_value={}))
        self.stack.enter_context(patch.object(harness.game_session, 'status', return_value={'restore_pending': False}))
        self.stack.enter_context(patch.object(harness.game_session, 'processes_in_prefix', return_value={42: 'identity'}))
        self.stack.enter_context(patch.object(harness, 'AppleTool', return_value=Mock(path=self.root / 'tool', status=lambda: {'policy': 'auto'})))
        self.commands = []
        def run(args, **kwargs):
            self.commands.append(args[-1])
            return subprocess.CompletedProcess(args, 0, 'closed\n', '')
        self.run = self.stack.enter_context(patch.object(harness.subprocess, 'run', side_effect=run))

    def check(self, **kwargs):
        return harness.check(self.root, 'highball', self.root / 'tool', 1, steam_only=True, idle_seconds=0, **kwargs)

    def report(self):
        return json.loads(next((self.root / 'DeadlockData/lifecycle-checks').glob('*/report.json')).read_text())

    def test_only_steam_commands_and_original_policy_are_recorded(self):
        result = self.check()
        self.assertEqual(self.commands, ['steam', 'steam-exit', 'steam-exit'])
        self.assertTrue(result['passed'])
        self.assertEqual(result['original_policy'], 'auto')
        self.assertIn('no game launch', result['scope'])
        self.assertIn('steam_exit_seconds', result['cycles'][0])

    def test_user_started_game_is_left_alone(self):
        self.games.side_effect = [{}, {99: 'game'}]
        with self.assertRaisesRegex(harness.ManagerError, 'without closing the game'):
            self.check()
        self.assertEqual(self.commands, ['steam'])
        self.assertFalse(self.report()['passed'])
        self.assertNotIn('cleanup', self.report())

    def test_failed_shutdown_is_not_retried_or_force_killed(self):
        self.run.side_effect = [subprocess.CompletedProcess([], 0, 'started', ''),
                                subprocess.CompletedProcess([], 1, '', 'Steam timed out')]
        with self.assertRaisesRegex(harness.ManagerError, 'steam-exit failed'):
            self.check()
        self.assertEqual(self.run.call_count, 2)
        self.assertFalse(self.report()['passed'])
        self.assertNotIn('cleanup', self.report())

    def test_existing_game_prevents_any_client_command(self):
        self.games.return_value = {99: 'game'}
        with self.assertRaisesRegex(harness.ManagerError, 'Close Deadlock'):
            self.check()
        self.run.assert_not_called()
