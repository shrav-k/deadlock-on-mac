from contextlib import ExitStack, redirect_stdout
from io import StringIO
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from deadlock_mac import game_exit, game_session
from deadlock_mac.runtime import exit_command, steam_control_command
from deadlock_mac.storage import ManagerError


class ExitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = {"id": "highball", "provider": "wine", "prefix": str(self.root / "Bottles/highball")}
        self.steam = Path(self.profile['prefix']) / 'drive_c/Program Files (x86)/Steam/steam.exe'
        self.steam.parent.mkdir(parents=True)
        self.steam.touch()
        self.receipt = {"workspace": str(self.root), "profile": "highball", "original_policy": "auto",
                        "restore_pending": False, "final_status": {"policy": "auto"}}

    def closing(self, *, games=None, identities=None, result=None):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(game_session, 'games_in_prefix', side_effect=games or [{42: 'identity'}, {}]))
        stack.enter_context(patch.object(game_session, 'processes_in_prefix', return_value={30: 'steam identity'}))
        stack.enter_context(patch.object(game_exit, 'environment', return_value={}))
        stack.enter_context(patch('deadlock_mac.runtime.wine_binary', return_value=Path('/wine')))
        run = stack.enter_context(patch.object(game_exit.subprocess, 'run', return_value=result or Mock(returncode=0)))
        stack.enter_context(patch.object(game_exit.game_mode, 'process_identity', side_effect=identities or ['identity', 'identity', '']))
        stack.enter_context(patch.object(game_session, 'status', return_value=self.receipt))
        stack.enter_context(patch.object(game_exit.time, 'sleep'))
        return run

    def test_steam_stop_waits_for_actual_exit_and_restore(self):
        run = self.closing()
        result = game_exit.close(self.root, self.profile, self.root / 'exit.log', report=Mock())
        self.assertIn('restored to auto', result)
        self.assertEqual(run.call_args.args[0], ['/wine', str(self.steam), '-ifrunning', '+app_stop', '1422450', '0'])
        self.assertEqual(run.call_args.kwargs['cwd'], self.profile['prefix'])
        self.assertEqual((self.root / 'exit.log').stat().st_mode & 0o777, 0o600)

    def test_no_game_never_starts_steam(self):
        with patch.object(game_session, 'games_in_prefix', return_value={}), patch.object(game_session, 'status', return_value={}), patch.object(game_exit, 'send') as send:
            self.assertIn('already closed', game_exit.close(self.root, self.profile, self.root / 'exit.log'))
        send.assert_not_called()

    def test_ambiguous_game_refuses_and_other_profile_policy_is_untouched(self):
        with patch.object(game_session, 'games_in_prefix', return_value={1: 'a', 2: 'b'}), self.assertRaisesRegex(ManagerError, 'Multiple'):
            game_exit.close(self.root, self.profile, self.root / 'exit.log')
        with patch.object(game_session, 'status', return_value={**self.receipt, 'profile': 'other', 'restore_pending': True}), patch.object(game_session, 'recover') as recover:
            game_exit.finish_session(self.root, 'highball')
        recover.assert_not_called()

    def test_pending_restore_is_not_reported_as_success(self):
        with patch.object(game_session, 'status', return_value={**self.receipt, 'restore_pending': True}), self.assertRaisesRegex(ManagerError, 'restoration is still pending'):
            game_exit.finish_session(self.root, 'highball', timeout=0)

    def test_still_starting_is_not_misreported_as_closed(self):
        with patch.object(game_session, 'status', return_value={**self.receipt, 'restore_pending': True, 'watcher_running': True, 'phase': 'waiting'}), self.assertRaisesRegex(ManagerError, 'still starting'):
            game_exit.finish_session(self.root, 'highball')

    def test_orphaned_session_recovers_prior_policy(self):
        with patch.object(game_session, 'status', side_effect=[{**self.receipt, 'restore_pending': True, 'recovery_needed': True}, self.receipt]), patch.object(game_session, 'recover') as recover, patch.object(game_exit.time, 'sleep'):
            self.assertIn('restored to auto', game_exit.finish_session(self.root, 'highball'))
        recover.assert_called_once_with()

    def test_unresponsive_game_never_signals_process_or_restores_policy(self):
        self.closing(identities=['identity'] * 10)
        with patch.object(game_exit, 'finish_session') as finish, patch.object(game_exit.os, 'kill') as kill, self.assertRaisesRegex(ManagerError, 'stop request did not close'):
            game_exit.close(self.root, self.profile, self.root / 'exit.log', timeout=0, report=Mock())
        kill.assert_not_called()
        finish.assert_not_called()

    def test_pid_reuse_before_command_prevents_stop(self):
        run = self.closing(identities=['new identity'])
        with self.assertRaisesRegex(ManagerError, 'changed'):
            game_exit.close(self.root, self.profile, self.root / 'exit.log')
        run.assert_not_called()

    def test_game_relaunch_during_close_does_not_claim_success(self):
        self.closing(games=[{42: 'identity'}, {55: 'another identity'}])
        with self.assertRaisesRegex(ManagerError, 'Another Deadlock process'):
            game_exit.close(self.root, self.profile, self.root / 'exit.log', report=Mock())

    def test_missing_steam_does_not_restart_client(self):
        run = self.closing()
        with patch.object(game_session, 'processes_in_prefix', return_value={}), self.assertRaisesRegex(ManagerError, 'Steam is not running'):
            game_exit.close(self.root, self.profile, self.root / 'exit.log')
        run.assert_not_called()

    def test_command_failure_and_timeout_do_not_claim_restoration(self):
        run = self.closing(games=[{42: 'identity'}] * 2, identities=['identity'] * 10, result=Mock(returncode=1))
        with patch.object(game_exit, 'finish_session') as finish:
            with self.assertRaisesRegex(ManagerError, 'Could not request'):
                game_exit.close(self.root, self.profile, self.root / 'failed.log')
            run.side_effect = subprocess.TimeoutExpired('steam', 15)
            with self.assertRaises(subprocess.TimeoutExpired):
                game_exit.close(self.root, self.profile, self.root / 'timed-out.log')
            finish.assert_not_called()

    def test_wine_and_crossover_use_app_stop_without_force(self):
        with patch('deadlock_mac.runtime.wine_binary', return_value=Path('/wine')):
            self.assertEqual(exit_command(self.profile)[-4:], ['-ifrunning', '+app_stop', '1422450', '0'])
            self.assertEqual(steam_control_command(self.profile, 'steam')[-2:], ['-ifrunning', '-shutdown'])
            with self.assertRaises(ManagerError):
                steam_control_command(self.profile, 'everything')
        app = self.root / 'CrossOver.app'
        binary = app / 'Contents/SharedSupport/CrossOver/bin/cxstart'
        binary.parent.mkdir(parents=True)
        binary.touch()
        result = exit_command({**self.profile, 'provider': 'crossover', 'runtime': str(app)})
        self.assertEqual(result[1:3], ['--bottle', self.profile['prefix']])
        self.assertEqual(result[-4:], ['-ifrunning', '+app_stop', '1422450', '0'])

    def test_steam_shutdown_waits_for_helpers_after_game_and_policy(self):
        calls = []
        def close(*args, **kwargs):
            calls.append('game restored')
            return 'game closed'
        def send(*args):
            self.assertEqual(calls, ['game restored'])
            calls.append('steam shutdown')
            return Mock(returncode=0)
        with patch.object(game_exit, 'close', side_effect=close), patch.object(game_exit, 'send', side_effect=send), patch.object(game_exit, 'steam_control_command', return_value=['steam', '-shutdown']), patch.object(game_session, 'games_in_prefix', return_value={}), patch.object(game_session, 'processes_in_prefix', side_effect=[{30: 'steam'}, {}, {31: 'helper'}, {}, {}, {}, {}]) as inspect, patch.object(game_exit, 'finish_session', return_value='restored'), patch.object(game_exit.time, 'sleep') as sleep:
            self.assertIn('helpers exited', game_exit.close_steam(self.root, self.profile, self.root / 'steam.log', report=Mock()))
        sleep.assert_called_once()
        self.assertTrue(all(call.args[0] == self.profile['prefix'] for call in inspect.call_args_list))

    def test_failed_game_close_prevents_steam_shutdown(self):
        with patch.object(game_exit, 'close', side_effect=ManagerError('game busy')), patch.object(game_exit, 'send') as send, self.assertRaisesRegex(ManagerError, 'game busy'):
            game_exit.close_steam(self.root, self.profile, self.root / 'steam.log')
        send.assert_not_called()

    def test_steam_helper_without_client_is_not_reported_as_closed(self):
        def inspect(prefix, name):
            return {31: 'helper'} if name == 'steamwebhelper.exe' else {}
        with patch.object(game_exit, 'close', return_value='closed'), patch.object(game_exit, 'send') as send, patch.object(game_session, 'games_in_prefix', return_value={}), patch.object(game_session, 'processes_in_prefix', side_effect=inspect), self.assertRaisesRegex(ManagerError, 'Steam is still running'):
            game_exit.close_steam(self.root, self.profile, self.root / 'steam.log', timeout=0, report=Mock())
        send.assert_not_called()

    def test_steam_shutdown_timeout_never_force_kills(self):
        with patch.object(game_exit, 'close', return_value='closed'), patch.object(game_exit, 'send', return_value=Mock(returncode=0)), patch.object(game_exit, 'steam_control_command', return_value=['steam', '-shutdown']), patch.object(game_session, 'games_in_prefix', return_value={}), patch.object(game_session, 'processes_in_prefix', return_value={30: 'steam'}), patch.object(game_exit.os, 'kill') as kill, self.assertRaisesRegex(ManagerError, 'Steam is still running'):
            game_exit.close_steam(self.root, self.profile, self.root / 'steam.log', timeout=0, report=Mock())
        kill.assert_not_called()

    def test_cli_routes_steam_exit_under_workspace_lock(self):
        from deadlock_mac.cli import main
        with patch('deadlock_mac.cli.load_profile', return_value=self.profile), patch.object(game_exit, 'close_steam', return_value='closed') as close, redirect_stdout(StringIO()):
            self.assertEqual(main(['--workspace', str(self.root), 'steam-exit']), 0)
        self.assertEqual(close.call_args.args[:2], (self.root, self.profile))
