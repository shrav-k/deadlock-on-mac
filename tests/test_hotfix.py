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
                            ("deadlock_mac.hotfix.previous_specification", {**self.spec, 'id': 'fix-v0'}),
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

    def previous(self):
        import shutil
        import json
        directory = self.root / 'Runtimes/fix-v0'
        shutil.copytree(self.root / 'Runtimes/fix-v1', directory)
        path = hotfix.receipt(self.root, self.profile)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'schema': 1, 'id': 'fix-v0', 'enabled': True}))
        return directory

    def test_existing_receipt_keeps_verified_previous_until_explicit_setup(self):
        previous = self.previous()
        self.assertEqual(hotfix.active(self.profile), previous)
        self.assertEqual(hotfix.status(self.profile)['id'], 'fix-v0')
        self.assertTrue(hotfix.install_available(self.root, self.profile))
        self.assertEqual(hotfix.status(self.profile)['id'], 'fix-v1')
        self.assertTrue(previous.is_dir())

    def test_explicit_previous_selection_survives_setup(self):
        self.previous()
        self.assertEqual(hotfix.configure(self.root, self.profile, True, previous=True)['id'], 'fix-v0')
        self.assertTrue(hotfix.install_available(self.root, self.profile))
        self.assertEqual(hotfix.status(self.profile)['id'], 'fix-v0')
        self.assertEqual(hotfix.configure(self.root, self.profile, True)['id'], 'fix-v1')

    def test_missing_new_payload_retains_previous_and_does_not_fake_upgrade(self):
        import shutil
        self.previous()
        shutil.rmtree(self.root / 'Runtimes/fix-v1')
        with patch.object(hotfix, 'REPO', self.root / 'no-bundle'):
            self.assertTrue(hotfix.install_available(self.root, self.profile))
        self.assertEqual(hotfix.status(self.profile)['id'], 'fix-v0')

    def test_corrupt_upgrade_keeps_previous_receipt(self):
        self.previous()
        self.file.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ManagerError, 'integrity'):
            hotfix.install_available(self.root, self.profile)
        self.assertEqual(hotfix.status(self.profile)['id'], 'fix-v0')

    def test_unknown_revision_cannot_select_arbitrary_path(self):
        import json
        self.previous()
        hotfix.receipt(self.root, self.profile).write_text(json.dumps({'enabled': True, 'id': '../other'}))
        with self.assertRaisesRegex(ManagerError, 'Unknown Wine hotfix revision'):
            hotfix.active(self.profile)

    def test_fresh_bundle_can_stage_current_and_previous_without_building(self):
        import shutil
        self.previous()
        bundle = self.root / 'app/runtime-overlays'
        shutil.copytree(self.root / 'Runtimes', bundle)
        shutil.rmtree(self.root / 'Runtimes')
        hotfix.receipt(self.root, self.profile).unlink()
        with patch.object(hotfix, 'REPO', self.root / 'app'):
            self.assertEqual(hotfix.configure(self.root, self.profile, True)['id'], 'fix-v1')
            self.assertEqual(hotfix.configure(self.root, self.profile, True, previous=True)['id'], 'fix-v0')
        self.assertTrue(self.file.is_file())

    def test_failed_bundle_staging_preserves_selected_revision(self):
        import shutil
        self.previous()
        bundle = self.root / 'app/runtime-overlays/fix-v1'
        shutil.copytree(self.root / 'Runtimes/fix-v1', bundle)
        shutil.rmtree(self.root / 'Runtimes/fix-v1')
        with patch.object(hotfix, 'REPO', self.root / 'app'), \
                patch.object(hotfix.shutil, 'copytree', side_effect=OSError('disk full')), \
                self.assertRaisesRegex(OSError, 'disk full'):
            hotfix.install_available(self.root, self.profile)
        self.assertEqual(hotfix.status(self.profile)['id'], 'fix-v0')
        self.assertEqual(sorted(p.name for p in (self.root / 'Runtimes').iterdir()), ['fix-v0'])
