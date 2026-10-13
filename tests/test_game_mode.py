from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from deadlock_mac import game_mode
from deadlock_mac.storage import ManagerError, atomic_json


class Tool:
    path = Path('/example/gamepolicyctl')

    def __init__(self, policy='auto'):
        self.policy = policy
        self.changes = []

    def status(self):
        return {'enabled': self.policy == 'on', 'policy': self.policy}

    def set(self, policy):
        self.changes.append(policy)
        self.policy = policy


class GameModeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.receipt = Path(self.temp.name).resolve() / 'recovery.json'

    def test_status_distinguishes_actual_mode_and_policy_with_apple_ansi_output(self):
        status = ('Game mode is \x1b[0;32mon\x1b[0;0m.\n'
                  'Game mode enablement policy is currently disabled. Game mode is forced always on.')
        self.assertEqual(game_mode.parse_status(status), {'enabled': True, 'policy': 'on'})
        self.assertEqual(game_mode.parse_status('Game mode is on.\nGame mode enablement policy is currently automatic.'),
                         {'enabled': True, 'policy': 'auto'})
        self.assertEqual(game_mode.parse_status('Game mode is off.\nGame mode is forced always off.'),
                         {'enabled': False, 'policy': 'off'})
        for bad in ('', 'dyld: missing symbol', 'Game mode is on.\nnew unknown policy',
                    'Game mode is on.\nGame mode is forced always on.\nGame mode is forced always off.'):
            with self.assertRaises(ManagerError):
                game_mode.parse_status(bad)

    def trial(self, tool, identities=None):
        with patch.object(game_mode, 'process_identity', side_effect=identities or ['start C:\\deadlock.exe']), \
                patch.object(game_mode.time, 'monotonic', side_effect=[0, 1]), \
                patch.object(game_mode.signal, 'signal'):
            return game_mode.trial(tool, 42, 1, self.receipt, report=lambda _: None)

    def test_deadline_restores_and_records_success(self):
        tool = Tool()
        self.assertEqual(self.trial(tool)['policy'], 'auto')
        self.assertEqual(tool.changes, ['on', 'auto'])
        self.assertFalse(json.loads(self.receipt.read_text())['restore_pending'])

    def test_process_exit_or_pid_reuse_ends_test(self):
        tool = Tool()
        with patch.object(game_mode, 'process_identity', side_effect=['start C:\\deadlock.exe', 'new C:\\deadlock.exe']), \
                patch.object(game_mode.time, 'monotonic', return_value=0), \
                patch.object(game_mode.time, 'sleep') as sleep, patch.object(game_mode.signal, 'signal'):
            game_mode.trial(tool, 42, 300, self.receipt, report=lambda _: None)
        sleep.assert_not_called()
        self.assertEqual(tool.policy, 'auto')

    def test_existing_override_and_wrong_process_never_mutate_policy(self):
        tool = Tool('off')
        with self.assertRaises(ManagerError):
            self.trial(tool)
        with self.assertRaises(ManagerError):
            self.trial(tool, ['start C:\\steam.exe'])
        self.assertEqual(tool.changes, [])
        self.assertFalse(self.receipt.exists())

    def test_failed_enable_after_mutation_still_restores(self):
        tool = Tool()
        original = tool.set

        def fail_after_on(policy):
            original(policy)
            if policy == 'on':
                raise ManagerError('request lost after mutation')

        tool.set = fail_after_on
        with self.assertRaisesRegex(ManagerError, 'request lost'):
            self.trial(tool)
        self.assertEqual(tool.policy, 'auto')
        self.assertFalse(json.loads(self.receipt.read_text())['restore_pending'])

    def test_termination_signal_restores_without_waiting_for_deadline(self):
        tool = Tool()
        installed = {}

        def install(sig, handler):
            installed[sig] = handler
            return None

        def set_policy(policy):
            tool.policy = policy
            if policy == 'on':
                installed[game_mode.signal.SIGTERM](None, None)

        with patch.object(game_mode, 'process_identity', return_value='start C:\\deadlock.exe'), \
                patch.object(game_mode.signal, 'signal', side_effect=install), \
                patch.object(tool, 'set', side_effect=set_policy), patch.object(game_mode.time, 'sleep') as sleep:
            game_mode.trial(tool, 42, 900, self.receipt, report=lambda _: None)
        sleep.assert_not_called()
        self.assertEqual(tool.policy, 'auto')
        self.assertFalse(json.loads(self.receipt.read_text())['restore_pending'])

    def test_restore_failure_retains_recovery_and_blocks_new_test(self):
        tool = Tool('on')
        atomic_json(self.receipt, {'schema': 1, 'original_policy': 'auto', 'restore_pending': True})
        with patch.object(tool, 'set', side_effect=ManagerError('service unavailable')):
            with self.assertRaises(ManagerError):
                game_mode.restore(tool, self.receipt)
        self.assertTrue(json.loads(self.receipt.read_text())['restore_pending'])
        with self.assertRaisesRegex(ManagerError, '--restore'):
            self.trial(Tool())

    def test_restore_respects_user_changed_policy(self):
        for policy in ('auto', 'off'):
            atomic_json(self.receipt, {'schema': 1, 'original_policy': 'auto', 'restore_pending': True})
            tool = Tool(policy)
            self.assertEqual(game_mode.restore(tool, self.receipt)['policy'], policy)
            self.assertEqual(tool.changes, [])

    def test_unsigned_binary_is_never_executed(self):
        candidate = Path(self.temp.name) / 'gamepolicyctl'
        candidate.write_text('not executable code')
        candidate.chmod(0o700)
        with patch.object(game_mode.platform, 'system', return_value='Darwin'), \
                patch.object(game_mode.subprocess, 'run') as run:
            run.return_value.returncode = 1
            with self.assertRaisesRegex(ManagerError, 'signature'):
                game_mode.AppleTool(candidate)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][0], '/usr/bin/codesign')

    def test_linked_recovery_receipt_never_changes_policy(self):
        target = self.receipt.with_name('target.json')
        atomic_json(target, {'schema': 1, 'original_policy': 'auto', 'restore_pending': True})
        self.receipt.symlink_to(target)
        tool = Tool('on')
        with self.assertRaisesRegex(ManagerError, 'symlink'):
            game_mode.restore(tool, self.receipt)
        self.assertEqual(tool.changes, [])

    def test_invalid_duration_precedes_any_process_or_tool_call(self):
        for seconds in (0, -1, 901, True):
            with self.assertRaises(ManagerError), patch.object(game_mode, 'process_identity') as identity:
                game_mode.trial(Tool(), 42, seconds, self.receipt)
            identity.assert_not_called()
