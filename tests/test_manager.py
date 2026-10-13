import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from deadlock_mac.backup import snapshot, wine_processes_running
from deadlock_mac.catalog import artifacts, catalog
from deadlock_mac.cli import create_profile, doctor, load_profile
from deadlock_mac.diagnostics import engine_dependencies
from deadlock_mac.runtime import clean_env, environment, launch_command, start, validate_profile
from deadlock_mac.steam import parse_vdf, game_status
from deadlock_mac.storage import ManagerError, atomic_json, download, identifier, lock, unpack, verify_extracted


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="Deadlock test ' $(touch SHOULD_NOT_EXIST) ")
        self.root = Path(self.temp.name).resolve()
        self.profile = {"schema": 1, "id": "free", "provider": "wine", "graphics": "dxmt",
                        "prefix": str(self.root / "Bottles/free"),
                        "runtime": str(self.root / "Runtime ' $special"),
                        "support": str(self.root / "Support"),
                        "dxmt": str(self.root / "DXMT")}
        support = Path(self.profile["support"]) / "libinotify.0.dylib"
        support.parent.mkdir()
        support.touch()
        self.steam = Path(self.profile["prefix"]) / "drive_c/Program Files (x86)/Steam/steam.exe"
        self.steam.parent.mkdir(parents=True)
        self.steam.touch()
        wine = Path(self.profile["runtime"]) / "bin/wine"
        wine.parent.mkdir(parents=True)
        wine.touch(mode=0o700)
        metal = Path(self.profile["dxmt"]) / "x86_64-unix/winemetal.so"
        metal.parent.mkdir(parents=True)
        metal.touch()

    def tearDown(self):
        self.temp.cleanup()

    def test_every_action_goes_through_steam_with_argv(self):
        for action, uri in (("launch", "steam://rungameid/1422450"),
                            ("install", "steam://install/1422450"), ("steam", "steam://open/main")):
            command = launch_command(self.profile, action)
            self.assertEqual(command[1:], [str(self.steam), uri])
            with patch("deadlock_mac.runtime.subprocess.Popen") as popen:
                start(self.profile, action, self.root / (action + ".log"))
                self.assertEqual(popen.call_args.args[0], command)
                self.assertNotIn("shell", popen.call_args.kwargs)
                self.assertEqual(popen.call_args.kwargs["cwd"], self.profile["prefix"])

    def test_missing_steam_never_launches_game_directly(self):
        self.steam.unlink()
        with self.assertRaises(ManagerError):
            launch_command(self.profile, "launch")

    def test_no_sensitive_or_conflicting_environment_leaks(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "secret", "WINEPREFIX": "/other",
                                     "DYLD_INSERT_LIBRARIES": "/bad", "CX_BOTTLE": "wrong"}):
            env = environment(self.profile)
        self.assertEqual(env["WINEPREFIX"], self.profile["prefix"])
        self.assertTrue(env["DYLD_FALLBACK_LIBRARY_PATH"].startswith(self.profile["support"] + ":"))
        for name in ("GITHUB_TOKEN", "DYLD_INSERT_LIBRARIES", "CX_BOTTLE"):
            self.assertNotIn(name, env)

    def test_profile_traversal_and_shared_prefix_rejected(self):
        for name in ("../free", "-x", "a/b", "x\n", "", "UPPER"):
            with self.assertRaises(ManagerError):
                identifier(name)
        profile = dict(self.profile, prefix=str(self.root / "Bottles/another"))
        with self.assertRaises(ManagerError):
            validate_profile(profile, self.root)

    def test_profile_recreation_preserves_existing_data(self):
        create_profile(self.root, "example")
        path = self.root / "DeadlockData/profiles/example.json"
        before = path.read_bytes()
        with self.assertRaises(ManagerError):
            create_profile(self.root, "example")
        self.assertEqual(path.read_bytes(), before)

    def test_free_families_use_distinct_engines_and_prefixes(self):
        create_profile(self.root, "new-highball", family="highball")
        create_profile(self.root, "new-sikarugir", family="sikarugir")
        highball = load_profile(self.root, "new-highball")
        sikarugir = load_profile(self.root, "new-sikarugir")
        self.assertNotEqual(highball["runtime"], sikarugir["runtime"])
        self.assertNotEqual(highball["prefix"], sikarugir["prefix"])
        env = environment(dict(self.profile, wine_family="highball"))
        self.assertNotIn("SikarugirAppWine11", env)
        self.assertEqual(env["WINEDLLPATH_PREPEND"], self.profile["dxmt"])
        self.assertEqual(env["DXMT_ALLOW_CROSS_PROCESS_SWAPCHAIN"], "1")

    def test_catalog_can_add_a_runtime_combination_without_cli_changes(self):
        config = self.root / "config"
        config.mkdir()
        value = catalog()
        value["runtimes"]["future-highball"] = dict(value["runtimes"]["highball"])
        (config / "runtime-lock.json").write_text(json.dumps({"artifacts": artifacts()}))
        (config / "runtimes.json").write_text(json.dumps(value))
        with patch("deadlock_mac.catalog.REPO", self.root):
            create_profile(self.root, "future", family="future-highball")
        profile = load_profile(self.root, "future")
        self.assertEqual(profile["runtime_set"], "future-highball")
        self.assertEqual(profile["wine_family"], "highball")

    def test_catalog_rejects_unknown_component_and_adapter(self):
        config = self.root / "config"
        config.mkdir()
        value = catalog()
        (config / "runtime-lock.json").write_text(json.dumps({"artifacts": artifacts()}))
        for key, bad in (("wine", "missing-artifact"), ("wine_family", "unknown-adapter")):
            original = value["runtimes"]["highball"][key]
            value["runtimes"]["highball"][key] = bad
            (config / "runtimes.json").write_text(json.dumps(value))
            with patch("deadlock_mac.catalog.REPO", self.root), self.assertRaises(ManagerError):
                catalog()
            value["runtimes"]["highball"][key] = original

    def test_atomic_write_failure_preserves_previous_state(self):
        path = self.root / "state.json"
        atomic_json(path, {"old": True})
        with patch("deadlock_mac.storage.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                atomic_json(path, {"new": True})
        self.assertEqual(json.loads(path.read_text()), {"old": True})
        self.assertFalse(list(self.root.glob(".write-*")))

    def test_state_write_and_lock_reject_symlinks(self):
        target = self.root / "outside.json"
        target.write_text("keep")
        link = self.root / "state.json"
        link.symlink_to(target)
        with self.assertRaises(ManagerError):
            atomic_json(link, {"changed": True})
        self.assertEqual(target.read_text(), "keep")
        folder = self.root / "linked"
        folder.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ManagerError):
            with lock(folder):
                pass

    def test_concurrent_writer_fails_then_lock_is_reusable(self):
        with lock(self.root):
            with self.assertRaises(ManagerError):
                with lock(self.root):
                    pass
        with lock(self.root):
            pass

    def test_cached_download_mismatch_fails_without_network(self):
        artifact = self.root / "bad.tar"
        artifact.write_bytes(b"tampered")
        with patch("urllib.request.build_opener") as network:
            with self.assertRaises(ManagerError):
                download("https://example.com/runtime.tar", "a" * 64, artifact)
            network.assert_not_called()
        self.assertEqual(artifact.read_bytes(), b"tampered")

    def test_archive_rejects_paths_links_and_devices(self):
        for index, (name, kind, link) in enumerate([
            ("../escape", tarfile.REGTYPE, ""), ("/absolute", tarfile.REGTYPE, ""),
            ("link", tarfile.SYMTYPE, "../../escape"),
            ("device", tarfile.CHRTYPE, "")]):
            archive = self.root / f"bad-{index}.tar"
            with tarfile.open(archive, "w") as tar:
                item = tarfile.TarInfo(name)
                item.type = kind
                item.linkname = link
                tar.addfile(item)
            dest = self.root / f"extracted-{index}"
            with self.assertRaises((ManagerError, tarfile.FilterError)):
                unpack(archive, dest)
            self.assertFalse(dest.exists())

    def test_archive_preserves_internal_links_and_executable(self):
        archive = self.root / "ok.tar"
        with tarfile.open(archive, "w") as tar:
            item = tarfile.TarInfo("runtime/bin/wine")
            item.size = 4
            item.mode = 0o755
            tar.addfile(item, io.BytesIO(b"test"))
            item = tarfile.TarInfo("runtime/bin/wine64")
            item.type = tarfile.SYMTYPE
            item.linkname = "wine"
            tar.addfile(item)
        dest = self.root / "extracted"
        unpack(archive, dest)
        self.assertEqual((dest / "runtime/bin/wine64").read_bytes(), b"test")
        self.assertTrue(os.access(dest / "runtime/bin/wine", os.X_OK))
        self.assertEqual(verify_extracted(archive, dest), 2)
        (dest / "runtime/bin/wine").write_text("changed")
        with self.assertRaises(ManagerError):
            verify_extracted(archive, dest)
        with self.assertRaises(ManagerError):
            unpack(archive, dest)

    def test_extraction_filters_out_unrequested_bundled_software(self):
        archive = self.root / "components.tar"
        with tarfile.open(archive, "w") as tar:
            for name in ("App/Frameworks/lib", "App/Frameworks/renderer/other", "App/MacOS/launcher"):
                item = tarfile.TarInfo(name)
                tar.addfile(item)
        dest = self.root / "components"
        args = dict(include="App/Frameworks", exclude=("App/Frameworks/renderer",))
        unpack(archive, dest, **args)
        self.assertTrue((dest / "App/Frameworks/lib").is_file())
        self.assertFalse((dest / "App/MacOS").exists())
        self.assertFalse((dest / "App/Frameworks/renderer").exists())
        self.assertEqual(verify_extracted(archive, dest, **args), 1)
        (dest / "unexpected-library").touch()
        with self.assertRaises(ManagerError):
            verify_extracted(archive, dest, **args)

    def test_backup_excludes_credentials_and_other_games(self):
        data = self.steam.parent / "userdata/12345/1422450/remote/settings.cfg"
        data.parent.mkdir(parents=True)
        data.write_text("game setting")
        (self.steam.parent / "ssfn123").write_text("credential")
        other = self.steam.parent / "userdata/12345/999/remote/save"
        other.parent.mkdir(parents=True)
        other.write_text("other game")
        result = snapshot(self.profile, self.root / "Backups", check_running=lambda: False)
        with zipfile.ZipFile(result) as archive:
            self.assertEqual(set(archive.namelist()), {
                "userdata/12345/1422450/remote/settings.cfg", "backup-manifest.json"})
        self.assertEqual(data.read_text(), "game setting")
        self.assertEqual(result.stat().st_mode & 0o777, 0o600)

    def test_backup_refuses_active_wine(self):
        with self.assertRaises(ManagerError):
            snapshot(self.profile, self.root / "Backups", check_running=lambda: True)
        self.assertFalse((self.root / "Backups").exists())

    def test_windows_process_paths_prevent_backup(self):
        for comm in (r"C:\Program Files (x86)\Steam\steam.exe", "/runtime/bin/wineserver"):
            with patch("deadlock_mac.backup.subprocess.run",
                       return_value=subprocess.CompletedProcess([], 0, comm, "")):
                self.assertTrue(wine_processes_running())

    def test_backup_rejects_files_created_during_snapshot(self):
        root = self.steam.parent / "userdata/12345/1422450"
        root.mkdir(parents=True)
        (root / "existing.cfg").write_text("before")
        original = zipfile.ZipFile.writestr
        def write_and_mutate(archive, name, data, **kwargs):
            result = original(archive, name, data, **kwargs)
            (root / "new.cfg").write_text("appeared during backup")
            return result
        with patch.object(zipfile.ZipFile, "writestr", write_and_mutate):
            with self.assertRaises(ManagerError):
                snapshot(self.profile, self.root / "Backups", check_running=lambda: False)
        self.assertFalse(list((self.root / "Backups").iterdir()))

    def test_backup_refuses_linked_game_data(self):
        data = self.steam.parent / "userdata/12345/1422450"
        data.parent.mkdir(parents=True)
        data.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ManagerError):
            snapshot(self.profile, self.root / "Backups", check_running=lambda: False)

    def test_report_has_no_account_or_machine_paths(self):
        report = json.dumps(doctor(self.root, self.profile))
        self.assertNotIn(str(self.root), report)
        self.assertNotIn("userdata", report)
        self.assertIn('"steam_installed": true', report)
        self.assertIn('"cloud": "unverified"', report)

    def test_dependency_check_reports_missing_library_without_host_paths(self):
        module = Path(self.profile["runtime"]) / "lib/wine/x86_64-unix/winedmo.so"
        module.parent.mkdir(parents=True)
        module.touch()
        listing = (str(module) + ':\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0)\n'
                   '\t/usr/local/opt/ffmpeg/lib/libavcodec.63.dylib (compatibility version 63.0.0)\n')
        with patch("deadlock_mac.diagnostics.platform.system", return_value="Darwin"), \
             patch("deadlock_mac.diagnostics.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 0, listing, "")):
            report = engine_dependencies(self.profile)
        self.assertEqual(report["unresolved"], [{"module": "winedmo.so", "library": "libavcodec.63.dylib"}])
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_download_manifest_is_not_a_completed_install(self):
        manifest = self.steam.parent / "steamapps/appmanifest_1422450.acf"
        manifest.parent.mkdir()
        manifest.write_text('"AppState" { "appid" "1422450" "StateFlags" "1026" "buildid" "0" }')
        self.assertFalse(game_status(self.steam)["installed"])
        manifest.write_text('"AppState" { "appid" "1422450" "StateFlags" "4" "buildid" "12345" }')
        self.assertTrue(game_status(self.steam)["installed"])
        self.assertEqual(game_status(self.steam)["build_id"], "12345")

    def test_crossover_uses_explicit_bottle_and_checks_signature(self):
        cx = self.root / "CrossOver.app/Contents/SharedSupport/CrossOver/bin/cxstart"
        cx.parent.mkdir(parents=True)
        cx.touch()
        profile = dict(self.profile, provider="crossover", graphics="vendor",
                       runtime=str(self.root / "CrossOver.app"))
        self.assertEqual(launch_command(profile, "launch"), [str(cx), "--bottle",
                         profile["prefix"], "steam://rungameid/1422450"])
        with patch("deadlock_mac.runtime.verify_crossover", side_effect=ManagerError("bad signature")):
            with patch("deadlock_mac.runtime.subprocess.Popen") as popen:
                with self.assertRaises(ManagerError):
                    start(profile, "launch", self.root / "cx.log")
                popen.assert_not_called()


class ManifestTest(unittest.TestCase):
    def test_nested_and_escaped_vdf(self):
        self.assertEqual(parse_vdf('// comment\n"AppState" { "appid" "1422450" "dir" "C:\\\\Games" }'),
                         {"AppState": {"appid": "1422450", "dir": "C:\\Games"}})

    def test_malformed_vdf_fails_closed(self):
        for text in ('"x" {', '"x" "y" garbage', '}','"x" "a" "x" "b"', '"x" }'):
            with self.subTest(text=text), self.assertRaises(ManagerError):
                parse_vdf(text)


if __name__ == "__main__":
    unittest.main()
