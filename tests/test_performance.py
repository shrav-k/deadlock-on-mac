import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadlock_mac import performance, game_settings, game_exit, runtime
from deadlock_mac.cli import bootstrap, setup
from deadlock_mac.diagnostics import display_status, power_status
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

    def native_fixture(self):
        values = {**game_settings.BALANCED_1080, **game_settings.NATIVE_RENDERING,
                  "setting.mat_viewportscale": "0.5", "setting.useadvanced": "0",
                  "setting.r_citadel_upscaling": "2", "setting.r_citadel_dlss_settings_mode": "1",
                  "setting.r_citadel_shadow_quality": "0", "private": "do not export"}
        self.video.write_bytes(('"video.cfg"\r\n{\r\n"Version" "20"\r\n' + ''.join(
            f'"{key}" "{value}"\r\n' for key, value in values.items()) + '}\r\n').encode())
        return self.video.read_bytes()

    def test_native_rendering_preserves_quality_resolution_and_exact_backup(self):
        original = self.native_fixture()
        self.assertFalse(game_settings.configure_native(self.root, self.profile)["applied"])
        self.assertEqual(original, self.video.read_bytes())
        result = game_settings.configure_native(self.root, self.profile, apply=True, check_running=lambda: False)
        self.assertEqual((Path(result["backup"]) / "video.txt").read_bytes(), original)
        values = parse_vdf(self.video.read_text())["video.cfg"]
        for key, value in game_settings.NATIVE_RENDERING.items():
            self.assertEqual(values[key], value)
        self.assertEqual(values["setting.r_citadel_shadow_quality"], "0")
        self.assertEqual(values["setting.defaultres"], "1920")
        self.assertEqual(self.video.read_bytes().count(b'\r\n'), original.count(b'\r\n'))

    def test_native_rendering_refuses_missing_keys_live_wine_and_changed_file(self):
        with self.assertRaisesRegex(ManagerError, "keys are missing"):
            game_settings.configure_native(self.root, self.profile, apply=True, check_running=lambda: False)
        original = self.native_fixture()
        with self.assertRaisesRegex(ManagerError, "Exit Windows Steam"):
            game_settings.configure_native(self.root, self.profile, apply=True, check_running=lambda: True)
        self.assertEqual(original, self.video.read_bytes())
        with self.assertRaisesRegex(ManagerError, "Wine started"):
            game_settings.configure_native(self.root, self.profile, apply=True, check_running=iter([False, True]).__next__)
        self.assertEqual(original, self.video.read_bytes())

    def test_graphics_snapshot_omits_unknown_values_and_detects_changes(self):
        self.native_fixture()
        self.video.with_name("machine_convars.vcfg").write_text('"config" { "convars" { "fps_max" "120" "fps_max_ui" "60" "private" "secret" } }')
        before = game_settings.rendering_snapshot(self.profile)
        self.assertTrue(before["available"])
        self.assertEqual(before["fps_limits"], {"fps_max": "120", "fps_max_ui": "60"})
        self.assertNotIn("secret", json.dumps(before))
        self.assertNotIn("do not export", json.dumps(before))
        self.assertNotIn("userdata", json.dumps(before))
        game_settings.configure_native(self.root, self.profile, apply=True, check_running=lambda: False)
        self.assertNotEqual(before["sha256"], game_settings.rendering_snapshot(self.profile)["sha256"])
        self.video.write_text('"video.cfg" { "Version" "21" }')
        self.assertFalse(game_settings.rendering_snapshot(self.profile)["available"])

    def test_sync_off_is_explicit_and_modes_are_exclusive(self):
        for mode in ("none", "msync", "esync"):
            env = performance.variables(dict(performance.DEFAULTS, sync=mode))
            self.assertEqual(env["WINEMSYNC"], "1" if mode == "msync" else "0")
            self.assertEqual(env["WINEESYNC"], "1" if mode == "esync" else "0")

    def test_highball_rejects_unsupported_esync_before_saving_or_launching(self):
        profile = {**self.profile, "wine_family": "highball"}
        settings = dict(performance.DEFAULTS, sync="esync")
        with self.assertRaisesRegex(ManagerError, "does not include ESync"):
            performance.save(self.root, profile, settings, check_running=lambda: False)
        self.assertFalse(performance.settings_path(self.root, "test").exists())
        with self.assertRaises(ManagerError):
            performance.validate_for_profile(settings, profile)
        self.assertEqual(performance.validate_for_profile(dict(settings, sync="msync"), profile)["sync"], "msync")

    def test_msync_exit_and_probe_environment_matches_launch_without_game_hud(self):
        support, dxmt, engine = (self.root / name for name in ("support", "dxmt", "engine"))
        for path in (support / "libinotify.0.dylib", dxmt / "x86_64-unix/winemetal.so"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        profile = {**self.profile, "wine_family": "highball", "support": str(support),
                   "dxmt": str(dxmt), "runtime": str(engine)}
        settings = dict(performance.DEFAULTS, sync="msync", metal_hud=True, hud_logging=True, fps_cap=60)
        performance.save(self.root, profile, settings, check_running=lambda: False)
        with patch("deadlock_mac.hotfix.active", return_value=None), \
                patch("deadlock_mac.media_runtime.library_directory", return_value=None):
            helper = runtime.environment(profile)
            launch = runtime.environment(profile, settings)
            self.assertEqual(helper["WINEMSYNC"], launch["WINEMSYNC"])
            self.assertEqual(helper["WINEMSYNC"], "1")
            self.assertEqual(helper["WINEESYNC"], "0")
            for key in ("MTL_HUD_ENABLED", "MTL_HUD_LOG_ENABLED", "DXMT_CONFIG"):
                self.assertNotIn(key, helper)
                self.assertIn(key, launch)
            with patch.object(game_exit.subprocess, "run") as run:
                game_exit.send(profile, ["wine", "steam.exe", "-shutdown"], self.root / "shutdown.log")
                self.assertEqual(run.call_args.kwargs["env"]["WINEMSYNC"], "1")
            # Existing unsupported receipts must also fail at launch, not silently
            # turn MSync off while claiming ESync was enabled.
            performance.settings_path(self.root, profile["id"]).write_text(json.dumps(dict(settings, sync="esync")))
            with self.assertRaisesRegex(ManagerError, "does not include ESync"):
                runtime.environment(profile)

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

    def test_borderless_recovery_preserves_quality_and_rejects_invalid_size(self):
        result = game_settings.configure(self.root, self.profile, apply=True, check_running=lambda: False,
                                         mode="borderless", width=1512, height=982)
        values = parse_vdf(self.video.read_text())["video.cfg"]
        self.assertEqual(values["setting.defaultres"], "1512")
        self.assertEqual(values["setting.fullscreen"], "0")
        self.assertEqual(values["setting.nowindowborder"], "1")
        self.assertEqual(values["setting.mat_viewportscale"], "0.73")
        self.assertTrue((Path(result["backup"]) / "video.txt").is_file())
        with self.assertRaises(ManagerError):
            game_settings.configure(self.root, self.profile, width=-1)

    def test_game_fps_preserves_line_endings_other_settings_and_backup(self):
        path = self.video.with_name("machine_convars.vcfg")
        original = b'"config"\r\n{\r\n"convars" { "fps_max" "400" "fps_max_ui" "120" "unrelated" "keep" }\r\n}\r\n'
        path.write_bytes(original)
        preview = game_settings.configure_fps(self.root, self.profile)
        self.assertEqual(preview["changes"]["fps_max"]["before"], "400")
        self.assertEqual(path.read_bytes(), original)
        result = game_settings.configure_fps(self.root, self.profile, apply=True, check_running=lambda: False)
        self.assertEqual(path.read_bytes(), original.replace(b'"400"', b'"60"').replace(b'"120"', b'"60"'))
        self.assertEqual((Path(result["backup"]) / path.name).read_bytes(), original)

    def test_game_fps_rejects_live_wine_unknown_format_duplicate_and_bad_cap(self):
        path = self.video.with_name("machine_convars.vcfg")
        with self.assertRaisesRegex(ManagerError, "Exit Windows Steam"):
            game_settings.configure_fps(self.root, self.profile, apply=True, check_running=lambda: True)
        for text in ('"config" { "unknown" {} }',
                     '"config" { "convars" { "fps_max" "400" "fps_max" "100" "fps_max_ui" "120" } }'):
            path.write_text(text)
            with self.assertRaises(ManagerError):
                game_settings.configure_fps(self.root, self.profile, apply=True, check_running=lambda: False)
            self.assertEqual(path.read_text(), text)
        for cap in (True, -1, 0, 361):
            with self.assertRaises(ManagerError):
                game_settings.configure_fps(self.root, self.profile, cap=cap)

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

    def test_display_report_excludes_serial_and_labels_desktop_scope(self):
        value = {"SPDisplaysDataType": [{"sppci_model": "GPU", "spdisplays_ndrvs": [
            {"_name": "Built-in", "_spdisplays_resolution": "1512 x 982", "_spdisplays_display-serial-number": "private"}]}]}
        with patch("deadlock_mac.diagnostics.platform.system", return_value="Darwin"), \
                patch("deadlock_mac.diagnostics.subprocess.run", return_value=type("R", (), {"stdout": json.dumps(value)})()):
            report = display_status()
        self.assertEqual(report["displays"][0]["desktop_mode"], "1512 x 982")
        self.assertNotIn("private", json.dumps(report))
        self.assertIn("not verification", report["scope"])

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
