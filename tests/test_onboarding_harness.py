"""Fresh-Xcode qualification must not pass using a legacy or provided fixture."""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import Mock, patch

from deadlock_mac import game_mode
from deadlock_mac.storage import ManagerError, sha256

SPEC = importlib.util.spec_from_file_location(
    'onboarding_harness', Path(__file__).resolve().parents[1] / 'packaging/check_onboarding.py')
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


class FreshXcodeQualificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / 'workspace'; self.workspace.mkdir()
        self.xcode = self.root / 'Xcode.app'
        self.source = self.xcode / 'Contents/Developer/usr/bin/gamepolicyctl'
        self.source.parent.mkdir(parents=True); self.source.write_bytes(b'new Apple tool fixture')
        (self.xcode / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': 'com.apple.dt.Xcode'}))
        (self.xcode / 'Contents/version.plist').write_bytes(plistlib.dumps(
            {'CFBundleShortVersionString': '27.1', 'ProductBuildVersion': 'test-build'}))
        self.cached = self.workspace / 'DeadlockData/tools/game-mode/new/gamepolicyctl'
        self.prepared = {'source': str(self.source), 'path': str(self.cached),
                         'sha256': sha256(self.source), 'status': {'policy': 'auto', 'enabled': False}}
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.run = self.stack.enter_context(patch.object(harness.subprocess, 'run', return_value=Mock(returncode=0)))
        self.tool = Mock(path=self.source)
        self.tool.status.return_value = {'policy': 'auto', 'enabled': False}
        self.apple = self.stack.enter_context(patch.object(game_mode, 'AppleTool', return_value=self.tool))
        self.prepare = self.stack.enter_context(patch.object(game_mode, 'prepare_tool', return_value=self.prepared))
        self.select = self.stack.enter_context(patch.object(game_mode, 'select_tool', return_value=Mock(path=self.cached)))

    def check(self):
        return harness.qualify_game_mode(self.workspace, require_xcode=self.xcode)

    def test_strict_pass_records_new_source_and_never_changes_policy(self):
        result = self.check()
        self.assertEqual(result['fresh_xcode_discovery'], 'passed')
        self.assertEqual(result['initial_tool_source'], str(self.source))
        self.assertEqual(result['tool_sha256'], sha256(self.source))
        self.assertEqual(result['xcode']['build'], 'test-build')
        self.assertTrue(result['xcode']['first_launch_complete'])
        self.assertEqual(self.run.call_args.kwargs['env']['DEVELOPER_DIR'], str(self.xcode / 'Contents/Developer'))
        self.assertEqual(result['policy_unchanged'], 'auto')
        self.assertEqual(self.prepare.call_args_list, [unittest.mock.call(self.workspace)] * 2)
        self.tool.set.assert_not_called()

    def test_strict_missing_or_incompatible_tool_cannot_be_reported_as_success(self):
        self.prepare.side_effect = ManagerError(game_mode.SETUP_HELP)
        with self.assertRaisesRegex(ManagerError, 'Install or update Xcode'):
            self.check()
        self.tool.set.assert_not_called()

    def test_incomplete_first_launch_stops_before_using_the_game_mode_tool(self):
        self.run.side_effect = [Mock(returncode=0), Mock(returncode=69)]
        with self.assertRaisesRegex(ManagerError, 'license and complete first-run'):
            self.check()
        self.apple.assert_not_called(); self.prepare.assert_not_called()

    def test_invalid_xcode_signature_prevents_executing_its_tools(self):
        self.run.return_value.returncode = 1
        with self.assertRaisesRegex(ManagerError, 'Apple signature'):
            self.check()
        self.assertEqual(self.run.call_count, 1)
        self.apple.assert_not_called(); self.prepare.assert_not_called()

    def test_optional_prerequisite_report_is_distinct_from_qualification(self):
        self.prepare.side_effect = ManagerError(game_mode.SETUP_HELP)
        result = harness.qualify_game_mode(self.workspace)
        self.assertEqual(result['initial_game_mode_discovery'], 'missing-compatible-Apple-tool-reported')
        self.assertNotIn('fresh_xcode_discovery', result)

    def test_explicit_fixture_remains_labelled_after_missing_xcode(self):
        self.prepare.side_effect = [ManagerError(game_mode.SETUP_HELP), self.prepared, self.prepared]
        result = harness.qualify_game_mode(self.workspace, apple_tool=self.source)
        self.assertEqual(result['initial_game_mode_discovery'], 'missing-compatible-Apple-tool-reported')
        self.assertEqual(result['provided_apple_tool'], 'signature/status/cache passed')
        self.assertNotIn('fresh_xcode_discovery', result)
        self.tool.set.assert_not_called()

    def test_unexpected_setup_error_is_not_downgraded_to_missing_prerequisite(self):
        self.prepare.side_effect = ManagerError('Prepared Apple tool failed integrity validation')
        with self.assertRaisesRegex(ManagerError, 'integrity'):
            harness.qualify_game_mode(self.workspace)

    def test_prior_cache_and_legacy_tool_are_rejected_before_execution(self):
        for relative in ('DeadlockData/tools/game-mode', 'Tools/game-mode-investigation/gamepolicyctl'):
            with self.subTest(relative=relative):
                path = self.workspace / relative; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'existing tool or receipt')
                with self.assertRaisesRegex(ManagerError, 'without cached or legacy'):
                    self.check()
                path.unlink()
        self.prepare.assert_not_called(); self.apple.assert_not_called()

    def test_wrong_discovered_source_and_wrong_digest_fail(self):
        for key, wrong in (('source', str(self.root / 'other/gamepolicyctl')), ('sha256', '0' * 64)):
            with self.subTest(key=key):
                self.prepare.return_value = {**self.prepared, key: wrong}
                with self.assertRaisesRegex(ManagerError, 'requested Xcode'):
                    self.check()
        self.select.assert_not_called()

    def test_policy_drift_fails_without_trying_to_override_other_apps(self):
        self.tool.status.side_effect = [{'policy': 'auto', 'enabled': False}, {'policy': 'off', 'enabled': False}]
        with self.assertRaisesRegex(ManagerError, 'policy changed'):
            self.check()
        self.tool.set.assert_not_called()

    def test_repeat_setup_must_reuse_the_new_tool(self):
        self.prepare.side_effect = [self.prepared, {**self.prepared, 'path': '/other/tool'}]
        with self.assertRaisesRegex(ManagerError, 'Repeat setup'):
            self.check()

    def test_fixture_override_cannot_be_combined_with_strict_discovery(self):
        with self.assertRaisesRegex(ManagerError, 'explicit tool fixture'):
            harness.qualify_game_mode(self.workspace, apple_tool=self.source, require_xcode=self.xcode)
        self.prepare.assert_not_called(); self.apple.assert_not_called()

    def test_tool_symlink_outside_xcode_is_rejected(self):
        outside = self.root / 'outside'; outside.write_bytes(b'other binary')
        self.source.unlink(); self.source.symlink_to(outside)
        with self.assertRaisesRegex(ManagerError, 'outside'):
            self.check()
        self.apple.assert_not_called()

    def test_non_xcode_bundle_cannot_qualify(self):
        (self.xcode / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': 'other.app'}))
        with self.assertRaisesRegex(ManagerError, 'not an Xcode'):
            self.check()
        self.apple.assert_not_called()
