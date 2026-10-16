import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from deadlock_mac import media_runtime
from deadlock_mac.storage import ManagerError, sha256


class MediaRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.id = 'ffmpeg-test'
        source = self.root / 'source' / self.id
        (source / 'lib').mkdir(parents=True)
        for name in ('lib/libavcodec.63.dylib', 'ffmpeg-source.tar.xz', 'COPYING.LGPLv2.1',
                     'provenance.json', 'build_media_runtime.py', 'config.h'):
            (source / name).write_text(name)
        self.spec = {'id': self.id, 'runtime_version': 'engine', 'libraries': {'libavcodec.63.dylib': 63},
                     'files': {'lib/libavcodec.63.dylib': sha256(source / 'lib/libavcodec.63.dylib')},
                     'inputs': {'ffmpeg': {'filename': 'ffmpeg-source.tar.xz', 'sha256': sha256(source / 'ffmpeg-source.tar.xz')}}}
        self.source = source
        self.archive = self.root / 'payload.tar.xz'
        with tarfile.open(self.archive, 'w:xz') as archive:
            archive.add(source, arcname=self.id)
        self.addCleanup(patch.stopall)
        patch.object(media_runtime, 'specification', return_value=self.spec).start()
        patch.object(media_runtime, 'runtime_set', return_value={'wine': 'engine'}).start()

    def test_clean_install_is_atomic_idempotent_and_does_not_need_compiler(self):
        with patch.object(media_runtime, 'package', return_value=self.archive) as package, \
                patch.object(media_runtime.subprocess, 'run') as run:
            first = media_runtime.install(self.root)
            second = media_runtime.install(self.root)
        self.assertEqual(first, second)
        package.assert_called_once(); run.assert_not_called()
        self.assertFalse(list((self.root / 'Runtimes').glob('.media-install-*')))
        self.assertEqual(media_runtime.library_directory({'provider': 'wine', 'runtime_version': 'engine',
                        'prefix': str(self.root / 'Bottles/test')}), first / 'lib')

    def test_corrupt_payload_does_not_publish_partial_install(self):
        self.spec['files']['lib/libavcodec.63.dylib'] = '0'*64
        with patch.object(media_runtime, 'package', return_value=self.archive), self.assertRaisesRegex(ManagerError, 'integrity'):
            media_runtime.install(self.root)
        self.assertFalse((self.root / 'Runtimes' / self.id).exists())
        self.assertFalse(list((self.root / 'Runtimes').glob('.media-install-*')))

    def test_wrong_abi_name_and_missing_source_are_rejected(self):
        path = self.source / 'lib/libavcodec.63.dylib'
        path.rename(path.with_name('libavcodec.61.dylib'))
        with self.assertRaisesRegex(ManagerError, 'integrity'):
            media_runtime.verify(self.source)
        path.with_name('libavcodec.61.dylib').rename(path)
        (self.source / 'ffmpeg-source.tar.xz').unlink()
        with self.assertRaisesRegex(ManagerError, 'corresponding-source'):
            media_runtime.verify(self.source)

    def test_tampered_install_and_unexpected_files_are_preserved_and_rejected(self):
        with patch.object(media_runtime, 'package', return_value=self.archive):
            installed = media_runtime.install(self.root)
        extra = installed / 'unknown'; extra.write_text('keep')
        with self.assertRaisesRegex(ManagerError, 'unexpected'):
            media_runtime.install(self.root)
        self.assertEqual(extra.read_text(), 'keep')

    def test_other_runtime_is_not_modified_or_required_to_use_these_libraries(self):
        with patch.object(media_runtime, 'runtime_set', return_value={'wine': 'other'}), \
                patch.object(media_runtime, 'package') as package:
            self.assertIsNone(media_runtime.install(self.root))
        package.assert_not_called()
        self.assertIsNone(media_runtime.library_directory({'runtime_version': 'other', 'provider': 'wine'}))

    def test_linked_runtime_and_linked_library_are_rejected(self):
        link = self.root / 'linked'; link.symlink_to(self.source, target_is_directory=True)
        with self.assertRaisesRegex(ManagerError, 'symlink'):
            media_runtime.verify(link)
        library = self.source / 'lib/libavcodec.63.dylib'
        library.unlink(); library.symlink_to(self.source / 'config.h')
        with self.assertRaisesRegex(ManagerError, 'symlink'):
            media_runtime.verify(self.source)

    def test_sealed_app_uses_bundled_payload_without_network_or_build(self):
        (self.root / 'runtime-payloads').mkdir()
        bundled = self.root / 'runtime-payloads' / (self.id + '.tar.xz'); bundled.write_bytes(b'sealed payload')
        with patch.object(media_runtime, 'REPO', self.root), patch.object(media_runtime.subprocess, 'run') as run:
            self.assertEqual(media_runtime.package(self.root / 'empty-downloads'), bundled)
        run.assert_not_called()
