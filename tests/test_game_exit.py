import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from deadlock_mac import game_exit
from deadlock_mac.runtime import exit_command
from deadlock_mac.storage import ManagerError


class ExitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = {"id": "highball", "provider": "wine", "prefix": str(self.root / "Bottles/highball")}
        self.receipt = {"workspace": str(self.root), "profile": "highball", "original_policy": "auto",
                        "restore_pending": False, "final_status": {"policy": "auto"}}

    def test_close_posts_normal_request_then_waits_for_actual_exit_and_restore(self):
        with patch.object(game_exit.game_session, "games_in_prefix", return_value={42: "identity"}), \
                patch.object(game_exit, "environment", return_value={}), \
                patch.object(game_exit, "exit_command", return_value=["wine", "taskkill.exe", "/IM", "deadlock.exe"]), \
                patch.object(game_exit.subprocess, "run", return_value=Mock(returncode=0)) as run, \
                patch.object(game_exit.game_mode, "process_identity", side_effect=["identity", ""]), \
                patch.object(game_exit.game_session, "status", return_value=self.receipt), \
                patch.object(game_exit.time, "sleep"):
            result = game_exit.close(self.root, self.profile, self.root / "exit.log", report=Mock())
        self.assertIn("restored to auto", result)
        self.assertNotIn("/F", run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["cwd"], self.profile["prefix"])
        self.assertEqual((self.root / "exit.log").stat().st_mode & 0o777, 0o600)

    def test_no_game_never_starts_taskkill(self):
        with patch.object(game_exit.game_session, "games_in_prefix", return_value={}), \
                patch.object(game_exit.game_session, "status", return_value={}), \
                patch.object(game_exit.subprocess, "run") as run:
            self.assertIn("already closed", game_exit.close(self.root, self.profile, self.root / "exit.log"))
        run.assert_not_called()

    def test_ambiguous_game_refuses_and_other_profile_policy_is_untouched(self):
        with patch.object(game_exit.game_session, "games_in_prefix", return_value={1: "a", 2: "b"}), \
                self.assertRaisesRegex(ManagerError, "Multiple"):
            game_exit.close(self.root, self.profile, self.root / "exit.log")
        with patch.object(game_exit.game_session, "status", return_value={**self.receipt, "profile": "other", "restore_pending": True}), \
                patch.object(game_exit.game_session, "recover") as recover:
            game_exit.finish_session(self.root, "highball")
        recover.assert_not_called()

    def test_pending_restore_is_not_reported_as_success(self):
        with patch.object(game_exit.game_session, "status", return_value={**self.receipt, "restore_pending": True}), \
                self.assertRaisesRegex(ManagerError, "restoration is still pending"):
            game_exit.finish_session(self.root, "highball", timeout=0)

    def test_unresponsive_game_times_out_without_signal_or_policy_change(self):
        with patch.object(game_exit.game_session, "games_in_prefix", return_value={42: "identity"}), \
                patch.object(game_exit, "environment", return_value={}), \
                patch.object(game_exit, "exit_command", return_value=["wine", "taskkill.exe", "/IM", "deadlock.exe"]), \
                patch.object(game_exit.subprocess, "run", return_value=Mock(returncode=0)), \
                patch.object(game_exit.game_mode, "process_identity", return_value="identity"), \
                patch.object(game_exit, "finish_session") as finish, \
                patch.object(game_exit.os, "kill") as kill, \
                self.assertRaisesRegex(ManagerError, "has not exited"):
            game_exit.close(self.root, self.profile, self.root / "exit.log", timeout=0, report=Mock())
        kill.assert_not_called()
        finish.assert_not_called()

    def test_wine_and_crossover_command_never_force_kill(self):
        with patch("deadlock_mac.runtime.wine_binary", return_value=Path("/wine")):
            self.assertEqual(exit_command(self.profile), ["/wine", "taskkill.exe", "/IM", "deadlock.exe"])
        app = self.root / "CrossOver.app"
        binary = app / "Contents/SharedSupport/CrossOver/bin/cxstart"
        binary.parent.mkdir(parents=True)
        binary.touch()
        result = exit_command({**self.profile, "provider": "crossover", "runtime": str(app)})
        self.assertEqual(result[1:3], ["--bottle", self.profile["prefix"]])
        self.assertNotIn("/F", result)
