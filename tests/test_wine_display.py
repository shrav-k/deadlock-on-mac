from pathlib import Path
import tempfile
import unittest

from deadlock_mac import wine_display
from deadlock_mac.storage import ManagerError


class WineDisplayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        prefix = self.root / "Bottles/test"
        prefix.mkdir(parents=True)
        self.profile = {"id": "test", "provider": "wine", "prefix": str(prefix)}
        self.registry = prefix / "user.reg"
        self.unrelated = '[Unrelated] 1\n"private-account-data"="must-not-back-up"\n'
        self.original = 'WINE REGISTRY Version 2\n\n' + self.unrelated
        self.registry.write_text(self.original)

    def configure(self, mode=None, **kwargs):
        return wine_display.configure(self.root, self.profile, mode, **kwargs)

    def test_preview_no_mutation_apply_and_exact_value_rollback(self):
        self.assertFalse(self.configure("on")["applied"])
        self.assertEqual(self.registry.read_text(), self.original)
        result = self.configure("on", apply=True, check_running=lambda: False)
        self.assertTrue(wine_display.status(self.profile)["enabled"])
        self.assertIn(self.unrelated, self.registry.read_text())
        backup = self.root / "DeadlockData/display-backups/test" / result["backup_id"] / "receipt.json"
        self.assertNotIn("must-not-back-up", backup.read_text())
        self.configure(restore=result["backup_id"], apply=True, check_running=lambda: False)
        self.assertIsNone(wine_display.status(self.profile)["value"])
        self.assertIn(self.unrelated, self.registry.read_text())

    def test_existing_section_crlf_other_values_and_restore_casing(self):
        content = self.original + f'\n[{wine_display.KEY}] 1\n#time=abc\n"RetinaMode"="Y"\n"Other"="keep"\n\n[Next]\n"RetinaMode"="n"\n'
        self.registry.write_bytes(content.replace("\n", "\r\n").encode())
        original = self.registry.read_bytes()
        result = self.configure("off", apply=True, check_running=lambda: False)
        self.assertFalse(wine_display.status(self.profile)["enabled"])
        self.configure(restore=result["backup_id"], apply=True, check_running=lambda: False)
        self.assertEqual(self.registry.read_bytes(), original)

    def test_running_wine_and_concurrent_change_are_refused(self):
        with self.assertRaisesRegex(ManagerError, "Exit Windows Steam"):
            self.configure("on", apply=True, check_running=lambda: True)
        self.assertEqual(self.registry.read_text(), self.original)
        checks = 0

        def race():
            nonlocal checks
            checks += 1
            if checks == 2:
                self.registry.write_text(self.original + '# changed by another writer\n')
            return False

        with self.assertRaisesRegex(ManagerError, "registry changed"):
            self.configure("on", apply=True, check_running=race)
        self.assertNotIn('"RetinaMode"', self.registry.read_text())
        self.assertIn("another writer", self.registry.read_text())

    def test_unknown_formats_duplicate_values_and_symlinks_are_refused(self):
        section = f'[{wine_display.KEY}]\n'
        for content in ("", "WINE REGISTRY Version 3\n", self.original + section + section,
                        self.original + section + '"RetinaMode"=dword:00000001\n',
                        self.original + section + '"RetinaMode"="y"\n"RetinaMode"="n"\n'):
            self.registry.write_text(content)
            with self.assertRaises(ManagerError):
                self.configure("on", apply=True, check_running=lambda: False)
            self.assertEqual(self.registry.read_text(), content)
        self.registry.unlink()
        target = self.root / "outside.reg"
        target.write_text(self.original)
        self.registry.symlink_to(target)
        with self.assertRaises(ManagerError):
            self.configure("on", apply=True, check_running=lambda: False)
        self.assertEqual(target.read_text(), self.original)

    def test_cross_profile_restore_and_traversal_are_refused(self):
        result = self.configure("on", apply=True, check_running=lambda: False)
        receipt = self.root / "DeadlockData/display-backups/test" / result["backup_id"] / "receipt.json"
        receipt.write_text(receipt.read_text().replace('"test"', '"other"'))
        with self.assertRaisesRegex(ManagerError, "Invalid Retina backup"):
            self.configure(restore=result["backup_id"], apply=True, check_running=lambda: False)
        with self.assertRaises(ManagerError):
            self.configure(restore="../../wrong", apply=True, check_running=lambda: False)
        self.assertTrue(wine_display.status(self.profile)["enabled"])
