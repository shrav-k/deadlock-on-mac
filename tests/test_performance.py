import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadlock_mac import performance, game_settings
from deadlock_mac.cli import bootstrap, setup
from deadlock_mac.diagnostics import power_status
from deadlock_mac.steam import parse_vdf
from deadlock_mac.storage import ManagerError


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.prefix = self.root / "Bottles/test"
        self.steam = self.prefix / "drive_c/Program Files (x86)/Steam/steam.exe"
        self.steam.parent.mkdir(parents=True)
        self.steam.touch()
        self.profile = {"provider": "wine", "id": "test", "prefix": str(self.prefix)}
        self.video = self.steam.parent / "userdata/123/1422450/local/cfg/video.txt"
        self.video.parent.mkdir(parents=True)
        self.original = '"video.cfg"\n{\n"Version" "20"\n' + "\n".join(
            f'"{k}" "0"' for k in game_settings.BALANCED_1080) + '\n"setting.mat_viewportscale" "0.73"\n}\n'
        self.video.write_text(self.original)

    def test_defaults_preserve_engine_sync_and_shader_cache(self):
        self.assertEqual(performance.variables(performance.load(self.root, "test")), {})
        settings = dict(performance.DEFAULTS, fps_cap=60, metal_hud=True, hud_logging=True)
        variables = performance.variables(settings)
        self.assertEqual(variables["DXMT_CONFIG"], "d3d11.preferredMaxFrameRate=60;")
        self.assertEqual(variables["MTL_HUD_LOG_ENABLED"], "1")
        self.assertNotIn("DXMT_SHADER_CACHE", variables)
        self.assertNotIn("WINEMSYNC", variables)

    def test_sync_off_is_explicit_and_modes_are_exclusive(self):
        for mode in ("none", "msync", "esync"):
            env = performance.variables(dict(performance.DEFAULTS, sync=mode))
            self.assertEqual(env["WINEMSYNC"], "1" if mode == "msync" else "0")
            self.assertEqual(env["WINEESYNC"], "1" if mode == "esync" else "0")

    def test_changes_require_closed_wine_and_preserve_previous_settings(self):
        performance.save(self.root, self.profile, dict(performance.DEFAULTS, fps_cap=60), check_running=lambda: False)
        with self.assertRaises(ManagerError):
            performance.save(self.root, self.profile, dict(performance.DEFAULTS, fps_cap=120), check_running=lambda: True)
        self.assertEqual(performance.load(self.root, "test")["fps_cap"], 60)

    def test_invalid_launch_values_rejected(self):
        for overrides in ({"fps_cap": True}, {"fps_cap": -1}, {"fps_cap": 361}, {"sync": "shell"},
                          {"hud_logging": True}, {"metal_hud": "1"}, {"unknown": 1}):
            with self.assertRaises(ManagerError):
                performance.validate(dict(performance.DEFAULTS, **overrides))

    def test_graphics_preview_preserves_bytes_and_apply_keeps_backup(self):
        self.assertFalse(game_settings.configure(self.root, self.profile)["applied"])
        self.assertEqual(self.video.read_text(), self.original)
        result = game_settings.configure(self.root, self.profile, apply=True, check_running=lambda: False)
        self.assertEqual((Path(result["backup"]) / "video.txt").read_text(), self.original)
        current = parse_vdf(self.video.read_text())["video.cfg"]
        self.assertEqual(current["setting.defaultres"], "1920")
        self.assertEqual(current["setting.mat_viewportscale"], "0.73")
        self.assertEqual(json.loads((Path(result["backup"]) / "receipt.json").read_text())["schema"], 1)

    def test_graphics_refuses_live_game_unknown_schema_and_multiple_accounts(self):
        with self.assertRaises(ManagerError):
            game_settings.configure(self.root, self.profile, apply=True, check_running=lambda: True)
        self.video.write_text(self.original.replace('"20"', '"21"'))
        with self.assertRaises(ManagerError):
            game_settings.configure(self.root, self.profile)
        self.video.write_text(self.original)
        other = self.steam.parent / "userdata/456/1422450/local/cfg/video.txt"
        other.parent.mkdir(parents=True)
        other.write_text(self.original)
        with self.assertRaises(ManagerError):
            game_settings.configure(self.root, self.profile)

    def test_bootstrap_preflight_precedes_downloads(self):
        with patch("deadlock_mac.cli.preflight", side_effect=ManagerError("Rosetta missing")), \
                patch("deadlock_mac.cli.install_runtimes") as install:
            with self.assertRaisesRegex(ManagerError, "Rosetta"):
                bootstrap(self.root, "test", "highball")
            install.assert_not_called()

    def test_power_report_is_scoped_to_active_source(self):
        with patch("deadlock_mac.diagnostics.platform.system", return_value="Darwin"), \
                patch("deadlock_mac.diagnostics.subprocess.run") as run:
            run.side_effect = [type("R", (), {"stdout": "Now drawing from 'AC Power'\nprivate battery id"})(),
                               type("R", (), {"stdout": "Battery Power:\n lowpowermode 1\nAC Power:\n lowpowermode 0\n"})()]
            self.assertEqual(power_status(), {"source": "AC Power", "low_power_mode": False})

    def test_setup_does_not_reinitialize_a_running_environment(self):
        with patch("deadlock_mac.cli.preflight"), \
                patch("deadlock_mac.cli.wine_processes_running", return_value=True), \
                patch("deadlock_mac.cli.install_runtimes") as install, \
                patch("deadlock_mac.cli.subprocess.run") as run:
            with self.assertRaisesRegex(ManagerError, "Exit Windows Steam"):
                bootstrap(self.root, "test", "highball")
            with self.assertRaisesRegex(ManagerError, "reinitialized"):
                setup(self.root, self.profile)
            install.assert_not_called()
            run.assert_not_called()
