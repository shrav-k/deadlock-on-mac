import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from deadlock_mac import hotfix
from deadlock_mac.storage import ManagerError


class HotfixTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = {"id": "highball", "provider": "wine", "wine_family": "highball",
                        "runtime_version": "pinned", "prefix": str(self.root / "Bottles/highball")}
        self.spec = {"id": "fix-v1", "runtime_version": "pinned", "files": {
            "x86_64-windows/sechost.dll": hashlib.sha256(b"reviewed").hexdigest()}}
        self.file = self.root / "Runtimes/fix-v1/x86_64-windows/sechost.dll"
        self.file.parent.mkdir(parents=True)
        self.file.write_bytes(b"reviewed")
        for name, value in (("deadlock_mac.hotfix.specification", self.spec),
                            ("deadlock_mac.backup.wine_processes_running", False)):
            mock = patch(name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_activation_rollback_and_tamper_fail_closed(self):
        self.assertIsNone(hotfix.active(self.profile))
        self.assertTrue(hotfix.configure(self.root, self.profile, True)["verified"])
        self.file.write_bytes(b"corrupted")
        with self.assertRaisesRegex(ManagerError, "integrity"):
            hotfix.active(self.profile)
        self.assertFalse(hotfix.configure(self.root, self.profile, False)["enabled"])

    def test_runtime_mismatch_and_live_activation_refused(self):
        with self.assertRaisesRegex(ManagerError, "pinned Highball"):
            hotfix.configure(self.root, {**self.profile, "runtime_version": "newer"}, True)
        with patch("deadlock_mac.backup.wine_processes_running", return_value=True), \
                self.assertRaisesRegex(ManagerError, "Exit Windows Steam"):
            hotfix.configure(self.root, self.profile, True)

    def test_linked_dll_refused_even_if_bytes_match(self):
        self.file.unlink()
        other = self.root / "outside.dll"
        other.write_bytes(b"reviewed")
        self.file.symlink_to(other)
        with self.assertRaisesRegex(ManagerError, "symlink"):
            hotfix.configure(self.root, self.profile, True)

    def test_bootstrap_stages_bundle_and_preserves_explicit_rollback(self):
        import shutil
        source = self.root / "app/runtime-overlays/fix-v1"
        source.parent.mkdir(parents=True)
        shutil.copytree(self.root / "Runtimes/fix-v1", source)
        shutil.rmtree(self.root / "Runtimes/fix-v1")
        with patch.object(hotfix, "REPO", self.root / "app"):
            self.assertTrue(hotfix.install_available(self.root, self.profile))
            self.assertEqual(self.file.read_bytes(), b"reviewed")
            hotfix.configure(self.root, self.profile, False)
            self.assertFalse(hotfix.install_available(self.root, self.profile))

    def test_new_runtime_does_not_inherit_existing_overlay(self):
        hotfix.configure(self.root, self.profile, True)
        with self.assertRaisesRegex(ManagerError, "does not match"):
            hotfix.active({**self.profile, "runtime_version": "new-base"})
