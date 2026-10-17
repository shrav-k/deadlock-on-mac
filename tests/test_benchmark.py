import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from deadlock_mac import benchmark
from deadlock_mac.storage import ManagerError


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.log = self.root / "DeadlockData/logs/highball/steam.log"
        self.log.parent.mkdir(parents=True)
        self.log.write_text("Private Steam login content must never appear in report.\n")
        self.profile = {"id": "highball", "prefix": str(self.root / "Bottles/highball")}
        for name, value in (("game_session.games_in_prefix", {123: "game identity"}),
                            ("game_log", self.log), ("snapshot", {}), ("hotfix.status", {}),
                            ("performance.load", {"hud_logging": True}), ("steam_path", self.root / "steam.exe"),
                            ("game_status", {"build_id": "1234"}), ("now", "2026-10-13T12:00:00")):
            mock = patch("deadlock_mac.benchmark." + name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_start_mark_finish_reads_only_game_samples_and_exports_allowlisted_metadata(self):
        run = benchmark.start(self.root, self.profile, "Mina", "1920x1200")
        benchmark.mark(self.root, self.profile, run["id"], "ultimate")
        with self.log.open("a") as stream:
            stream.write("2026-10-13 12:00:01.000 wine[456:1] metal-HUD: 1,0,44,1000,1\n")
            stream.write("2026-10-13 12:00:01.000 wine[123:1] metal-HUD: 1,0,44,10,2,20,4,60,8\n")
        with patch.object(benchmark, "now", return_value="2026-10-13T12:01:00"):
            report = benchmark.finish(self.root, self.profile, run["id"])
        self.assertEqual(report["metrics"]["presentation_samples"], 3)
        self.assertEqual(report["metrics"]["samples_over_50_ms"], 1)
        self.assertEqual(report["markers"][0]["label"], "ultimate")
        self.assertNotIn("log", report)
        self.assertNotIn("process_identity", report)
        self.assertNotIn("login content", json.dumps(report))
        with self.assertRaisesRegex(ManagerError, "not recording"):
            benchmark.finish(self.root, self.profile, run["id"])

    def test_rotated_or_missing_samples_are_not_successful_benchmarks(self):
        run = benchmark.start(self.root, self.profile, "sandbox", "1512x982")
        self.log.rename(self.log.with_suffix(".old"))
        self.log.write_text("new file")
        with self.assertRaisesRegex(ManagerError, "replaced or truncated"):
            benchmark.finish(self.root, self.profile, run["id"])

    def test_other_profile_cannot_finish_recording(self):
        run = benchmark.start(self.root, self.profile, "sandbox", "1512x982")
        with self.assertRaisesRegex(ManagerError, "not recording"):
            benchmark.finish(self.root, {**self.profile, "id": "other"}, run["id"])

    def test_graphics_drift_is_recorded_without_claiming_comparable_settings(self):
        for after, expected in (({"available": True, "sha256": "first"}, True),
                                ({"available": True, "sha256": "changed"}, False),
                                ({"available": True, "sha256": "first", "fps_limits": {"fps_max": "120"}}, False),
                                ({"available": False}, None)):
            with patch.object(benchmark.game_settings, "rendering_snapshot", side_effect=[
                    {"available": True, "sha256": "first"}, after]), \
                    patch.object(benchmark, "summarize", return_value={}):
                run = benchmark.start(self.root, self.profile, "native-low", "2560x1440")
                report = benchmark.finish(self.root, self.profile, run["id"])
                self.assertIs(report["saved_graphics_unchanged"], expected)
                self.assertEqual(report["graphics_after"], after)


class LogDiscoveryTests(unittest.TestCase):
    def test_redirected_stdout_uses_manager_stderr_without_reading_other_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            log = root / "DeadlockData/logs/highball/steam.log"
            log.parent.mkdir(parents=True)
            log.touch()
            result = Mock(returncode=0, stdout=f"p123\nn/dev/null\nn{log}\n")
            with patch.object(benchmark.subprocess, "run", return_value=result) as run:
                self.assertEqual(benchmark.game_log(root, 123), log)
            self.assertIn("1,2", run.call_args.args[0])
            with patch.object(benchmark.subprocess, "run", return_value=Mock(returncode=0, stdout="p123\nn/etc/private\n")), \
                    self.assertRaisesRegex(ManagerError, "uniquely locate"):
                benchmark.game_log(root, 123)
