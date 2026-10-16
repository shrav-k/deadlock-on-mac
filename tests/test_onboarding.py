import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from deadlock_mac import cli, game_mode
from deadlock_mac.storage import ManagerError, sha256


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_discovery_skips_signed_but_incompatible_xcode(self):
        old, current = self.root / 'old', self.root / 'current'
        failing = Mock(); failing.status.side_effect = ManagerError('incompatible macOS')
        working = Mock(path=current); working.status.return_value = {'enabled': False, 'policy': 'auto'}
        with patch.object(game_mode, 'tool_candidates', return_value=[old, current]), \
                patch.object(game_mode, 'AppleTool', side_effect=[failing, working]):
            self.assertIs(game_mode.select_tool(self.root), working)
        failing.set.assert_not_called(); working.set.assert_not_called()

    def test_no_tool_has_actionable_setup_error_and_no_policy_change(self):
        with patch.object(game_mode, 'tool_candidates', return_value=[]), \
                patch.object(game_mode, 'AppleTool') as tool, self.assertRaisesRegex(ManagerError, 'Install or update Xcode'):
            game_mode.select_tool(self.root)
        tool.assert_not_called()

    def test_prepare_is_idempotent_offline_and_survives_source_removal(self):
        source = self.root / 'provided/gamepolicyctl'; source.parent.mkdir(); source.write_bytes(b'fake signed tool')
        tools = []
        def make_tool(path):
            tool = Mock(path=Path(path))
            tool.status.return_value = {'enabled': False, 'policy': 'auto'}
            tools.append(tool)
            return tool
        with patch.object(game_mode, 'AppleTool', side_effect=make_tool):
            first = game_mode.prepare_tool(self.root, source)
            cached = Path(first['path']); source.unlink()
            second = game_mode.prepare_tool(self.root, cached)
        self.assertEqual(first['path'], second['path'])
        self.assertEqual(sha256(cached), first['sha256'])
        self.assertTrue(all(not tool.set.called for tool in tools))
        with patch.object(game_mode.subprocess, 'run', return_value=Mock(returncode=1)), \
                patch.object(Path, 'glob', return_value=[]):
            self.assertEqual(list(game_mode.tool_candidates(self.root)), [cached])

    def test_corrupt_cached_tool_is_never_a_discovery_candidate(self):
        directory = self.root / 'DeadlockData/tools/game-mode'
        path = directory / ('a'*64) / 'gamepolicyctl'; path.parent.mkdir(parents=True); path.write_text('changed')
        (directory / 'current.json').write_text(json.dumps({'sha256': 'a'*64}))
        with patch.object(game_mode.subprocess, 'run', return_value=Mock(returncode=1)), \
                patch.object(Path, 'glob', return_value=[]):
            self.assertNotIn(path, list(game_mode.tool_candidates(self.root)))

    def test_receipt_cannot_redirect_discovery_outside_managed_cache(self):
        directory = self.root / 'DeadlockData/tools/game-mode'; directory.mkdir(parents=True)
        (directory / 'current.json').write_text(json.dumps({'sha256': '../../outside', 'path': '/malicious/tool'}))
        with patch.object(game_mode.subprocess, 'run', return_value=Mock(returncode=1)), \
                patch.object(Path, 'glob', return_value=[]):
            self.assertEqual(list(game_mode.tool_candidates(self.root)), [])

    def test_setup_checks_game_mode_before_download_or_wine_and_opt_out_is_explicit(self):
        with patch.object(cli, 'preflight'), patch.object(cli, 'wine_processes_running', return_value=False), \
                patch.object(game_mode, 'prepare_tool', side_effect=ManagerError('Install or update Xcode')) as prepare, \
                patch.object(cli, 'install_runtimes') as install, patch.object(cli, 'setup') as setup:
            with self.assertRaisesRegex(ManagerError, 'Xcode'):
                cli.bootstrap(self.root, 'fresh', 'highball')
            install.assert_not_called(); setup.assert_not_called()
            with patch.object(cli, 'create_profile'), patch.object(cli, 'load_profile', return_value={}), \
                    patch.object(cli.hotfix, 'install_available', return_value=False), \
                    patch.object(cli.hotfix, 'compatible', return_value=False):
                cli.bootstrap(self.root, 'fresh', 'highball', without_game_mode=True)
            self.assertEqual(prepare.call_count, 1)
            install.assert_called_once(); setup.assert_called_once()

    def test_setup_rejects_active_wine_before_preparing_any_tool(self):
        with patch.object(cli, 'preflight'), patch.object(cli, 'wine_processes_running', return_value=True), \
                patch.object(game_mode, 'prepare_tool') as prepare, self.assertRaisesRegex(ManagerError, 'Exit Windows Steam'):
            cli.bootstrap(self.root, 'fresh', 'highball')
        prepare.assert_not_called()
