import json
import os
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stdout
from io import StringIO

from deadlock_mac import game_mode, game_session
from deadlock_mac.storage import ManagerError, atomic_json, lock
from test_game_mode import Tool


class GameSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.receipt = self.root / 'session.json'
        self.profile = {'id': 'highball', 'prefix': str(self.root / 'Bottles/highball')}
        self.identity = 'Tue Oct 13 12:00:00 2026 C:\\Steam\\deadlock.exe'

    def run_session(self, tool, identities=('',), candidates=None, launch=None, ready=None, sleep=None):
        identities = iter(identities)

        def identity(pid):
            return 'watcher' if pid == os.getpid() else next(identities)

        with patch.object(game_mode, 'process_identity', side_effect=identity), \
                patch.object(game_session, 'games_in_prefix', side_effect=candidates or [{42: self.identity}]), \
                patch.object(game_session.time, 'sleep', side_effect=sleep), \
                patch.object(game_session.signal, 'signal'), \
                patch.object(game_session.time, 'monotonic', side_effect=range(0, 100000, 3600)):
            game_session.session(tool, self.profile, self.root, self.receipt,
                                 launch or Mock(), ready or Mock())

    def test_no_play_deadline_and_exact_prior_policy_restored(self):
        for policy in ('auto', 'on', 'off'):
            tool = Tool(policy)
            ticks = []

            def tick(_):
                ticks.append(1)
                self.assertEqual(tool.policy, 'on')
                self.assertTrue(json.loads(self.receipt.read_text())['restore_pending'])

            # Simulated clock moves forward hours during a live game, not five minutes.
            self.run_session(tool, [self.identity] * 4 + [''], sleep=tick)
            self.assertEqual(len(ticks), 4)
            self.assertEqual(tool.policy, policy)
            state = json.loads(self.receipt.read_text())
            self.assertEqual(state['original_policy'], policy)
            self.assertFalse(state['restore_pending'])
            self.assertNotIn('maximum_seconds', state)

    def test_startup_timeout_restores_and_records_reason(self):
        tool = Tool('off')
        launch = Mock()
        with self.assertRaisesRegex(ManagerError, 'did not start'):
            self.run_session(tool, candidates=[{}, {}], launch=launch)
        launch.assert_called_once()
        self.assertEqual(tool.policy, 'off')
        self.assertIn('did not start', json.loads(self.receipt.read_text())['error'])

    def test_steam_launch_failure_restores_before_success_ack(self):
        tool = Tool()
        ready = Mock()
        with self.assertRaisesRegex(ManagerError, 'Steam failed'):
            self.run_session(tool, candidates=[{}], launch=Mock(side_effect=ManagerError('Steam failed')), ready=ready)
        ready.assert_not_called()
        self.assertEqual(tool.policy, 'auto')

    def test_timeout_uses_only_this_launch_log_and_restores_policy(self):
        tool = Tool('off')
        log = self.root / 'launch.log'
        log.write_text('fatal stalled cross-thread pipe')
        with patch.object(game_mode, 'process_identity', return_value='watcher'), \
                patch.object(game_session, 'games_in_prefix', return_value={}), \
                patch.object(game_session.signal, 'signal'), \
                patch.object(game_session.time, 'monotonic', side_effect=[0, 200]), \
                self.assertRaisesRegex(ManagerError, 'Steam reported a stalled main loop'):
            game_session.session(tool, self.profile, self.root, self.receipt, Mock(), Mock(), startup_log=log)
        state = json.loads(self.receipt.read_text())
        self.assertEqual(state['launch_log'], str(log))
        self.assertFalse(state['restore_pending'])
        self.assertEqual(tool.policy, 'off')

    def test_a_recovered_steam_warning_does_not_abort_a_running_game(self):
        log = self.root / 'launch.log'
        log.write_text('CSteamEngine::BMainLoop appears to have stalled')
        tool = Tool()
        with patch.object(game_mode, 'process_identity', side_effect=['watcher', '']), \
                patch.object(game_session, 'games_in_prefix', return_value={42: self.identity}), \
                patch.object(game_session.signal, 'signal'):
            game_session.session(tool, self.profile, self.root, self.receipt, Mock(), Mock(), startup_log=log)
        self.assertNotIn('error', json.loads(self.receipt.read_text()))
        self.assertEqual(tool.policy, 'auto')

    def test_failed_enable_after_mutation_restores(self):
        tool = Tool('off')
        change = tool.set

        def fail(policy):
            change(policy)
            if policy == 'on':
                raise ManagerError('lost reply')

        tool.set = fail
        with self.assertRaisesRegex(ManagerError, 'lost reply'):
            self.run_session(tool)
        self.assertEqual(tool.policy, 'off')

    def test_pid_reuse_is_exit_and_existing_game_is_not_relaunched(self):
        tool = Tool()
        launch = Mock()
        self.run_session(tool, ['new start C:\\Steam\\deadlock.exe'], launch=launch)
        launch.assert_not_called()
        self.assertEqual(tool.policy, 'auto')

    def test_session_keeps_policy_on_until_exit(self):
        tool = Tool()
        ticks = []

        def tick(_):
            self.assertEqual(tool.policy, 'on')
            ticks.append(1)
            tool.policy = 'off'

        self.run_session(tool, [self.identity, self.identity, ''], sleep=tick)
        self.assertEqual(len(ticks), 2)
        self.assertEqual(tool.changes, ['on', 'on', 'auto'])

    def test_termination_restores_even_while_waiting_for_game(self):
        tool = Tool()
        handlers = {}

        def install(sig, handler):
            handlers[sig] = handler

        def ready():
            handlers[signal.SIGTERM](None, None)

        with patch.object(game_mode, 'process_identity', return_value='watcher'), \
                patch.object(game_session, 'games_in_prefix', return_value={}), \
                patch.object(game_session.signal, 'signal', side_effect=install):
            game_session.session(tool, self.profile, self.root, self.receipt, Mock(), ready)
        self.assertEqual(tool.policy, 'auto')

    def test_failed_restore_keeps_recoverable_receipt(self):
        tool = Tool()
        change = tool.set

        def fail(policy):
            if policy == 'auto':
                raise ManagerError('service unavailable')
            change(policy)

        tool.set = fail
        with self.assertRaisesRegex(ManagerError, 'service unavailable'):
            self.run_session(tool)
        state = json.loads(self.receipt.read_text())
        self.assertEqual(state['phase'], 'restore-failed')
        self.assertTrue(state['restore_pending'])

    def test_recovery_refuses_active_game_or_another_watcher(self):
        tool = Tool()
        self.run_session(tool)
        state = json.loads(self.receipt.read_text())
        state['restore_pending'] = True
        atomic_json(self.receipt, state)
        with lock(self.root), self.assertRaises(ManagerError):
            game_session.recover(self.root)
        with patch.object(game_session, 'games_in_prefix', return_value={42: self.identity}), \
                self.assertRaisesRegex(ManagerError, 'still running'):
            game_session.recover(self.root)
        tool.policy = 'on'
        with patch.object(game_session, 'games_in_prefix', return_value={}), \
                patch.object(game_mode, 'AppleTool', return_value=tool):
            game_session.recover(self.root)
        self.assertEqual(tool.policy, 'auto')

    def test_resume_preserves_original_policy_instead_of_current_override(self):
        state = {'schema': 2, 'original_policy': 'off', 'restore_pending': True}
        tool = Tool('on')
        with patch.object(game_mode, 'process_identity', side_effect=['watcher', '']), \
                patch.object(game_session, 'games_in_prefix', return_value={42: self.identity}), \
                patch.object(game_session.signal, 'signal'):
            game_session.session(tool, self.profile, self.root, self.receipt, Mock(), Mock(), previous=state)
        self.assertEqual(tool.policy, 'off')

    def test_prefix_matching_uses_cwd_without_reading_environment(self):
        expected = self.profile['prefix'] + '/drive_c/Steam/steamapps/common/Deadlock/game'
        results = [Mock(returncode=0, stdout='p42\nn' + expected + '\n'),
                   Mock(returncode=0, stdout='p43\nn/another/bottle/game\n')]
        with patch.object(game_session, 'game_candidates', return_value=[42, 43]), \
                patch.object(game_session.subprocess, 'run', side_effect=results) as run, \
                patch.object(game_mode, 'process_identity', return_value=self.identity):
            self.assertEqual(game_session.games_in_prefix(self.profile['prefix']), {42: self.identity})
        self.assertEqual(run.call_args_list[0].args[0], ['/usr/sbin/lsof', '-a', '-p', '42', '-d', 'cwd', '-Fn'])

    def test_detached_launch_uses_isolated_interpreter_and_file_streams(self):
        log = self.root / 'launch.log'

        def spawn(command, **options):
            atomic_json(Path(command[-2]), {'ok': True, 'watcher_pid': 123})
            self.assertTrue(options['start_new_session'])
            self.assertEqual(command[1:3], ['-I', '-B'])
            self.assertNotEqual(options['stdout'], game_session.subprocess.PIPE)
            return Mock()

        with patch.object(game_session.subprocess, 'Popen', side_effect=spawn):
            self.assertEqual(game_session.launch_session(self.root, 'highball', Tool.path, log)['watcher_pid'], 123)

    def test_process_candidates_include_windows_paths_but_not_native_steam(self):
        rows = '1 /Applications/Steam.app/Contents/MacOS/steam_osx\n2 C:\\Steam\\steam.exe\n3 /bottle/drive_c/Steam/steam.exe\n4 /bottle/steamwebhelper.exe\n'
        with patch.object(game_session.subprocess, 'run', return_value=Mock(returncode=0, stdout=rows)):
            self.assertEqual(game_session.process_candidates('steam.exe'), [2, 3])

    def test_prefix_inspection_rejects_pid_reused_during_lsof(self):
        result = Mock(returncode=0, stdout='n' + self.profile['prefix'] + '\n')
        with patch.object(game_session.subprocess, 'run', return_value=result), \
                patch.object(game_mode, 'process_identity', side_effect=['old /Steam/steam.exe', 'new /Steam/steam.exe']):
            self.assertEqual(game_session.processes_in_prefix(self.profile['prefix'], 'steam.exe', [42]), {})

    def test_prefix_inspection_failure_does_not_assume_process_is_safe(self):
        with patch.object(game_session.subprocess, 'run', return_value=Mock(returncode=1)) as run, \
                patch.object(game_mode, 'process_identity', return_value='alive /Steam/steam.exe'), \
                patch.object(game_session.time, 'sleep') as sleep, \
                self.assertRaisesRegex(ManagerError, 'Could not identify'):
            game_session.processes_in_prefix(self.profile['prefix'], 'steam.exe', [42])
        self.assertEqual(run.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_helper_losing_cwd_before_exit_is_rechecked_without_false_failure(self):
        with patch.object(game_session.subprocess, 'run', return_value=Mock(returncode=1)) as run, \
                patch.object(game_mode, 'process_identity', side_effect=['alive /Steam/steamwebhelper.exe'] * 2 + ['']), \
                patch.object(game_session.time, 'sleep') as sleep:
            self.assertEqual(game_session.processes_in_prefix(self.profile['prefix'], 'steamwebhelper.exe', [42]), {})
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once_with(0.1)

    def test_transient_cwd_failure_still_identifies_the_live_owned_process(self):
        results = [Mock(returncode=1), Mock(returncode=0, stdout='n' + self.profile['prefix'] + '\n')]
        identity = 'alive /Steam/steamwebhelper.exe'
        with patch.object(game_session.subprocess, 'run', side_effect=results), \
                patch.object(game_mode, 'process_identity', return_value=identity), \
                patch.object(game_session.time, 'sleep'):
            self.assertEqual(game_session.processes_in_prefix(self.profile['prefix'], 'steamwebhelper.exe', [42]), {42: identity})

    def test_success_without_cwd_cannot_hide_a_live_process(self):
        with patch.object(game_session.subprocess, 'run', return_value=Mock(returncode=0, stdout='p42\n')), \
                patch.object(game_mode, 'process_identity', return_value='alive /Steam/steam.exe'), \
                patch.object(game_session.time, 'sleep'), \
                self.assertRaisesRegex(ManagerError, 'Could not identify'):
            game_session.processes_in_prefix(self.profile['prefix'], 'steam.exe', [42])

    def test_duplicate_worker_cannot_change_policy_or_launch_again(self):
        response = self.root / 'response.json'
        with lock(self.root), patch.object(game_session, 'state_directory', return_value=self.root), \
                patch.object(game_mode, 'AppleTool') as tool, patch.object(game_session, 'start') as start:
            self.assertEqual(game_session.worker(self.root, 'highball', Tool.path, response, self.root / 'launch.log'), 1)
        self.assertIn('already active', json.loads(response.read_text())['error'])
        tool.assert_not_called()
        start.assert_not_called()

    def test_manual_stop_only_signals_the_recorded_watcher_identity(self):
        self.run_session(Tool())
        state = json.loads(self.receipt.read_text())
        state.update(restore_pending=True, watcher_pid=987, watcher_identity='original watcher')
        atomic_json(self.receipt, state)
        with patch.object(game_mode, 'process_identity', return_value='different process'), \
                patch.object(game_session, 'recover', return_value={}) as recover, \
                patch.object(game_session.os, 'kill') as kill:
            game_session.stop_session(self.root)
        kill.assert_not_called()
        recover.assert_called_once_with(self.root)

    def test_worker_resumes_interrupted_running_game_with_original_policy(self):
        self.run_session(Tool('off'))
        state = json.loads(self.receipt.read_text())
        state['restore_pending'] = True
        atomic_json(self.receipt, state)
        with patch.object(game_session, 'state_directory', return_value=self.root), \
                patch('deadlock_mac.cli.load_profile', return_value=self.profile), \
                patch.object(game_session, 'games_in_prefix', return_value={42: self.identity}), \
                patch.object(game_mode, 'AppleTool', return_value=Tool('on')), \
                patch.object(game_session, 'session') as session:
            self.assertEqual(game_session.worker(self.root, 'highball', Tool.path,
                                                 self.root / 'response.json', self.root / 'launch.log'), 0)
        self.assertEqual(session.call_args.kwargs['previous']['original_policy'], 'off')

    def test_new_worker_uses_prepared_tool_for_session_and_recovery(self):
        cached = self.root / 'cached/gamepolicyctl'
        tool = Tool(); tool.path = cached
        with patch.object(game_session, 'state_directory', return_value=self.root), \
                patch('deadlock_mac.cli.load_profile', return_value=self.profile), \
                patch.object(game_mode, 'prepare_tool', return_value={'path': str(cached)}) as prepare, \
                patch.object(game_mode, 'AppleTool', return_value=tool) as constructor, \
                patch.object(game_session, 'session') as session:
            self.assertEqual(game_session.worker(self.root, 'highball', None,
                                                 self.root / 'response.json', self.root / 'launch.log'), 0)
        prepare.assert_called_once_with(self.root, None)
        constructor.assert_called_once_with(str(cached))
        self.assertIs(session.call_args.args[0], tool)

    def test_missing_apple_tool_fails_before_policy_change_or_steam_launch(self):
        response = self.root / 'response.json'
        with patch.object(game_session, 'state_directory', return_value=self.root), \
                patch('deadlock_mac.cli.load_profile', return_value=self.profile), \
                patch.object(game_mode, 'prepare_tool', side_effect=ManagerError('Install or update Xcode')), \
                patch.object(game_session, 'session') as session, \
                patch.object(game_session, 'start') as start:
            self.assertEqual(game_session.worker(self.root, 'highball', None,
                                                 response, self.root / 'launch.log'), 1)
        session.assert_not_called(); start.assert_not_called()
        self.assertFalse(self.receipt.exists())
        self.assertFalse(json.loads(response.read_text())['ok'])

    def test_cli_play_defaults_to_session_with_explicit_opt_out(self):
        from deadlock_mac.cli import main
        for arguments, automatic in ((['--game-mode-tool', str(Tool.path)], True),
                                     (['--without-game-mode'], False)):
            with patch('deadlock_mac.cli.load_profile', return_value=self.profile), \
                    patch('deadlock_mac.cli.performance.load', return_value={}), \
                    patch.object(game_session, 'launch_session', return_value={'watcher_pid': 42}) as session, \
                    patch('deadlock_mac.cli.start', return_value=43) as start, redirect_stdout(StringIO()):
                self.assertEqual(main(['--workspace', str(self.root), 'launch', *arguments]), 0)
            self.assertEqual(session.called, automatic)
            self.assertEqual(start.called, not automatic)
            if automatic:
                self.assertEqual(session.call_args.args[2], Tool.path)

    def test_interrupted_diagnostic_receipt_is_shared_across_workspaces(self):
        with patch.object(game_session, 'state_directory', return_value=self.root):
            receipt = self.root / 'game-mode-test.json'
            atomic_json(receipt, {'schema': 1, 'original_policy': 'auto', 'restore_pending': True})
            self.assertEqual(game_session.pending_trial(self.root / 'different-workspace'), receipt)


if __name__ == '__main__':
    unittest.main()
