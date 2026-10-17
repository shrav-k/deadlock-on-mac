"""Candidate audio checks must not silently replace the installed runtime."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('audio_harness', Path(__file__).resolve().parents[1] / 'packaging/check_audio.py')
harness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(harness)


class AudioCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.manifest = self.root / 'manifest.json'
        self.files = {}
        for arch in ('x86_64', 'i386'):
            name = arch + '-windows/winmm.dll'
            path = self.root / name
            path.parent.mkdir()
            path.write_bytes(arch.encode())
            self.files[name] = hashlib.sha256(arch.encode()).hexdigest()
        self.manifest.write_text(json.dumps(self.files))
        self.profile = {'wine_family': 'highball'}
        self.original = {'WINEDLLPATH_PREPEND': '/verified/exitfix:/verified/dxmt', 'WINEPREFIX': '/profile'}
        mocked = patch.object(harness, 'environment', side_effect=lambda _: dict(self.original))
        mocked.start()
        self.addCleanup(mocked.stop)

    def test_candidate_is_child_only_and_keeps_existing_overlays(self):
        env, files = harness.candidate_environment(self.profile, self.root, self.manifest)
        self.assertEqual(env['WINEDLLPATH_PREPEND'], str(self.root) + ':/verified/exitfix:/verified/dxmt')
        self.assertEqual(env['WINEPREFIX'], '/profile')
        self.assertEqual(files, self.files)
        unchanged, files = harness.candidate_environment(self.profile, None, None)
        self.assertEqual(unchanged, self.original)
        self.assertIsNone(files)

    def test_missing_manifest_and_unexpected_dll_fail(self):
        with self.assertRaisesRegex(harness.ManagerError, 'manifest is required'):
            harness.candidate_environment(self.profile, self.root, None)
        self.files['x86_64-windows/ntdll.dll'] = 'a' * 64
        self.manifest.write_text(json.dumps(self.files))
        with self.assertRaisesRegex(harness.ManagerError, 'exactly the two'):
            harness.candidate_environment(self.profile, self.root, self.manifest)

    def test_unreviewed_marker_is_not_an_accepted_digest(self):
        self.files['i386-windows/winmm.dll'] = 'UNREVIEWED'
        self.manifest.write_text(json.dumps(self.files))
        with self.assertRaisesRegex(harness.ManagerError, 'SHA-256'):
            harness.candidate_environment(self.profile, self.root, self.manifest)

    def test_candidate_bytes_and_loader_family_must_match(self):
        with self.assertRaisesRegex(harness.ManagerError, 'Highball'):
            harness.candidate_environment({'wine_family': 'another'}, self.root, self.manifest)
        (self.root / 'i386-windows/winmm.dll').write_bytes(b'changed')
        with self.assertRaisesRegex(harness.ManagerError, 'integrity'):
            harness.candidate_environment(self.profile, self.root, self.manifest)

    def test_running_wine_prevents_probe_or_profile_access(self):
        with patch.object(harness, 'wine_processes_running', return_value=True), \
                patch.object(harness, 'load_profile') as load, \
                self.assertRaisesRegex(harness.ManagerError, 'every Wine session'):
            harness.check(self.root, self.root, 'highball')
        load.assert_not_called()
