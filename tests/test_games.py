"""Game contracts use disposable fixtures, never a live Steam library or save."""
import contextlib
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from deadlock_mac import (benchmark, cli, displays, game_exit, game_mode,
                          game_session, game_settings, hotfix, runtime, steam, visual)
from deadlock_mac.core import steam as shared_steam, wine
from deadlock_mac.games import (binding, definitions, for_profile, from_receipt,
                               get_game, require_launch)
from deadlock_mac.storage import ManagerError, atomic_json
from test_game_mode import Tool


class GameContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.deadlock = get_game()
        self.elden = get_game("elden-ring-seamless")
        self.profile = {"schema": 1, "id": "test", "provider": "wine", "graphics": "dxmt",
                        "prefix": str(self.root / "Bottles/test"),
                        "runtime": str(self.root / "Runtime"), "dxmt": str(self.root / "DXMT"),
                        "support": str(self.root / "Support")}
        self.er_profile = {**self.profile, "schema": 2, **binding(self.elden)}
        self.steam = Path(self.profile["prefix"]) / "drive_c/Program Files (x86)/Steam/steam.exe"
        self.steam.parent.mkdir(parents=True)
        self.steam.touch()
        binary = Path(self.profile["runtime"]) / "bin/wine"
        binary.parent.mkdir(parents=True)
        binary.touch(mode=0o700)

    def test_legacy_imports_are_the_shared_implementations(self):
        self.assertIs(runtime, wine)
        self.assertIs(steam, shared_steam)

    def test_legacy_profile_read_does_not_migrate_or_rebind_it(self):
        path = cli.profile_file(self.root, "test")
        atomic_json(path, self.profile)
        original = path.read_bytes()
        self.assertEqual(for_profile(cli.load_profile(self.root, "test")), self.deadlock)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(runtime.launch_command(self.profile, "launch")[-1], "steam://rungameid/1422450")
        self.assertEqual(runtime.exit_command(self.profile)[-3:], ["+app_stop", "1422450", "0"])

    def test_new_profile_has_explicit_binding_and_cannot_replace_existing_profile(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.create_profile(self.root, "elden", game_id=self.elden.id)
        value = cli.load_profile(self.root, "elden")
        self.assertEqual(value["schema"], 2)
        self.assertEqual(for_profile(value), self.elden)
        before = cli.profile_file(self.root, "elden").read_bytes()
        with self.assertRaises(ManagerError):
            cli.create_profile(self.root, "elden", game_id="deadlock")
        self.assertEqual(cli.profile_file(self.root, "elden").read_bytes(), before)
        self.assertFalse(Path(value["prefix"]).exists())

    def test_unknown_incomplete_and_mismatched_bindings_are_rejected(self):
        for fields in ({"schema": True}, {"schema": 3}, {"schema": 2},
                       {"game_id": self.elden.id},
                       {"schema": 2, "game_id": "unknown", "game_recipe_version": 1},
                       {"schema": 2, "game_id": "deadlock", "game_recipe_version": 99},
                       {"schema": 2, "game_id": "deadlock", "game_recipe_version": True}):
            with self.subTest(fields=fields), self.assertRaises(ManagerError):
                runtime.validate_profile({**self.profile, **fields}, self.root)

    def test_recipe_identifiers_paths_and_dynamic_adapters_are_rejected(self):
        for field, value in (("id", "../other"), ("steam_app_id", "1245620;bad"),
                             ("steam_app_id", True), ("process_name", "../eldenring.exe"),
                             ("install_directory", "C:\\other"), ("install_directory", "../other"),
                             ("settings_adapter", "os.system"), ("version", True)):
            with self.subTest(field=field), self.assertRaises(ManagerError):
                replace(self.elden, **{field: value})

    def test_elden_install_is_correct_but_launch_never_falls_back_to_vanilla(self):
        self.assertEqual(runtime.launch_command(self.er_profile, "install")[-1], "steam://install/1245620")
        self.assertEqual(runtime.launch_command(self.er_profile, "steam")[-1], "steam://open/main")
        with patch.object(wine.subprocess, "Popen") as start, self.assertRaisesRegex(ManagerError, "DirectX 12"):
            runtime.start(self.er_profile, "launch", self.root / "launch.log")
        start.assert_not_called()
        self.assertFalse((self.root / "launch.log").exists())
        with self.assertRaisesRegex(ManagerError, "not yet qualified"):
            require_launch({**self.er_profile, "graphics": "vendor", "provider": "crossover"})
        with self.assertRaisesRegex(ManagerError, "mod launcher"):
            runtime.exit_command(self.er_profile)

    def test_shared_steam_manifest_never_uses_other_game_install_state(self):
        directory = self.steam.parent / "steamapps"
        directory.mkdir()
        deadlock = directory / "appmanifest_1422450.acf"
        deadlock.write_text('"AppState" { "appid" "1422450" "StateFlags" "4" }')
        self.assertTrue(steam.game_status(self.steam)["installed"])
        self.assertFalse(steam.game_status(self.steam, self.elden)["installed"])
        elden = directory / "appmanifest_1245620.acf"
        elden.write_text('"AppState" { "appid" "1245620" "StateFlags" "4" }')
        self.assertTrue(steam.game_status(self.steam, self.elden)["installed"])
        elden.write_bytes(deadlock.read_bytes())
        with self.assertRaisesRegex(ManagerError, "app manifest"):
            steam.game_status(self.steam, self.elden)

    def test_deadlock_graphics_backup_and_sdl_adapters_reject_elden_before_io(self):
        sentinel = self.steam.parent / "keep.txt"
        sentinel.write_text("existing data")
        for operation in (lambda: game_settings.configure(self.root, self.er_profile),
                          lambda: game_settings.configure_native(self.root, self.er_profile, apply=True),
                          lambda: game_settings.configure_fps(self.root, self.er_profile, apply=True),
                          lambda: displays.require_supported(self.er_profile),
                          lambda: displays.sdl_path(self.er_profile),
                          lambda: steam.data_roots(self.steam, self.elden)):
            with self.assertRaises(ManagerError):
                operation()
        self.assertEqual(sentinel.read_text(), "existing data")
        self.assertFalse((self.root / "DeadlockData").exists())
        self.assertFalse(game_settings.rendering_snapshot(self.er_profile)["available"])

    def test_deadlock_hotfix_does_not_leak_into_second_game(self):
        spec = hotfix.specification()
        base = {**self.profile, "wine_family": "highball", "runtime_version": spec["runtime_version"]}
        self.assertTrue(hotfix.compatible(base, spec))
        self.assertFalse(hotfix.compatible({**base, "schema": 2, **binding(self.elden)}, spec))

    def test_bootstrap_rejects_research_game_before_download_or_game_mode_change(self):
        atomic_json(cli.profile_file(self.root, "test"), self.er_profile)
        with patch.object(cli, "preflight") as check, patch.object(cli, "install_runtimes") as install, \
                patch.object(game_mode, "prepare_tool") as mode, self.assertRaises(ManagerError):
            cli.bootstrap(self.root, "test", "highball")
        check.assert_not_called()
        install.assert_not_called()
        mode.assert_not_called()

    def test_process_and_capture_selection_uses_game_identity(self):
        with patch.object(game_session, "process_candidates", return_value=[42]) as candidates, \
                patch.object(game_session, "processes_in_prefix", return_value={42: "elden"}) as processes:
            self.assertEqual(game_session.games_in_prefix(self.profile["prefix"], self.elden), {42: "elden"})
            candidates.assert_called_once_with("eldenring.exe")
            processes.assert_called_once_with(self.profile["prefix"], "eldenring.exe", [42])
            visual.candidates(self.er_profile, "game")
            self.assertEqual(processes.call_args.args, (self.profile["prefix"], "eldenring.exe"))
            with self.assertRaises(ManagerError):
                visual.candidates(self.er_profile, "deadlock")

    def test_legacy_receipts_keep_deadlock_and_incomplete_bindings_fail(self):
        self.assertEqual(from_receipt({}), self.deadlock)
        self.assertEqual(from_receipt(binding(self.elden)), self.elden)
        for value in ({"game_id": self.elden.id}, {"game_recipe_version": 1},
                      {"game_id": self.elden.id, "game_recipe_version": True}):
            with self.assertRaises(ManagerError):
                from_receipt(value)

    def test_session_refuses_adopting_other_game_before_policy_change(self):
        tool = Mock()
        with self.assertRaisesRegex(ManagerError, "another game"):
            game_session.session(tool, self.er_profile, self.root, self.root / "session.json", Mock(), Mock(),
                                 previous={"restore_pending": True, **binding(self.deadlock)})
        tool.set.assert_not_called()
        self.assertFalse((self.root / "session.json").exists())

    def test_watcher_rejects_unsupported_launch_before_preparing_game_mode(self):
        atomic_json(cli.profile_file(self.root, "test"), self.er_profile)
        response = self.root / "response.json"
        with patch.object(game_session, "state_directory", return_value=self.root / "mode"), \
                patch.object(game_mode, "prepare_tool") as prepare, contextlib.redirect_stdout(io.StringIO()):
            result = game_session.worker(self.root, "test", None, response, self.root / "launch.log")
        self.assertEqual(result, 1)
        prepare.assert_not_called()
        self.assertFalse((self.root / "mode/session.json").exists())

    def test_shared_session_tracks_final_game_identity_and_restores_policy(self):
        # Exercise the shared service with a fake running game, not a launch claim.
        tool = Tool("off")
        receipt = self.root / "session.json"
        with patch.object(game_session, "games_in_prefix", return_value={42: "eldenring identity"}) as games, \
                patch.object(game_mode, "process_identity", side_effect=lambda pid: "watcher" if pid == os.getpid() else ""), \
                patch.object(game_session.signal, "signal"):
            game_session.session(tool, self.er_profile, self.root, receipt, Mock(), Mock())
        games.assert_called_once_with(self.er_profile["prefix"], self.elden)
        state = json.loads(receipt.read_text())
        self.assertEqual(from_receipt(state), self.elden)
        self.assertEqual(state["phase"], "finished")
        self.assertFalse(state["restore_pending"])
        self.assertEqual(tool.policy, "off")

    def test_recovery_checks_receipts_game_not_deadlock(self):
        receipt = self.root / "session.json"
        atomic_json(receipt, {"schema": 2, "original_policy": "auto", "restore_pending": True,
                             "prefix": self.er_profile["prefix"], "tool": "/unused", **binding(self.elden)})
        with patch.object(game_session, "games_in_prefix", return_value={42: "eldenring identity"}) as games, \
                patch.object(game_mode, "AppleTool") as tool, self.assertRaisesRegex(ManagerError, "still running"):
            game_session.recover(self.root)
        games.assert_called_once_with(self.er_profile["prefix"], self.elden)
        tool.assert_not_called()

    def test_display_benchmark_and_input_receipts_cannot_cross_game(self):
        atomic_json(displays.state_path(self.root, self.er_profile), {"schema": 1, "profile": "test", **binding(self.deadlock)})
        with self.assertRaises(ManagerError):
            displays.load(self.root, self.er_profile)
        atomic_json(benchmark.folder(self.root) / "test-run.json", {"profile": "test", "phase": "recording"})
        with self.assertRaises(ManagerError):
            benchmark.load(self.root, self.er_profile, "test-run")
        state = {"schema": 1, "profile": "test", "prefix": self.er_profile["prefix"],
                 "target": "game", "input_used": False, "created_at": 10, **binding(self.deadlock)}
        with self.assertRaises(ManagerError):
            visual.validate_input(state, self.er_profile, "key", key="escape", now=11)
        with patch.object(game_session, "status", return_value={"workspace": str(self.root), "profile": "test"}), \
                self.assertRaisesRegex(ManagerError, "another game"):
            game_exit.finish_session(self.root, "test", game=self.elden)

    def test_game_info_is_read_only_and_explains_capability_gap(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(["--workspace", str(self.root), "game-info", self.elden.id]), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["steam_app_id"], "1245620")
        self.assertFalse(result["settings_writable"])
        self.assertIn("DirectX 12", " ".join(result["launch_blockers"]))
        self.assertFalse((self.root / "DeadlockData").exists())


if __name__ == "__main__":
    unittest.main()
