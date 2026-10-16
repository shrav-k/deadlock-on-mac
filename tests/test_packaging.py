"""Fault injection for app publication; no downloads, signing or GUI required."""
import importlib.util
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('build_app', Path(__file__).resolve().parents[1] / 'packaging/build_app.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / 'Manager.app'

    def test_failed_build_cleans_staging_without_publishing_partial_app(self):
        def fail(output, *_):
            (output / 'Contents').mkdir(parents=True)
            raise RuntimeError('compiler failed')
        with patch.object(builder, 'build_staged', side_effect=fail), self.assertRaisesRegex(RuntimeError, 'compiler failed'):
            builder.build(self.output, self.root / 'downloads')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_output_is_preserved_without_starting_build(self):
        self.output.mkdir()
        sentinel = self.output / 'existing'
        sentinel.write_text('keep')
        with patch.object(builder, 'build_staged') as build, self.assertRaises(SystemExit):
            builder.build(self.output, self.root / 'downloads')
        self.assertEqual(sentinel.read_text(), 'keep')
        build.assert_not_called()

    def test_success_publishes_app_and_manifest_together_after_verification(self):
        def stage(output, *_):
            self.assertFalse(self.output.exists())
            output.mkdir()
            (output / 'verified').write_text('yes')
            output.with_suffix('.sha256.json').write_text('{}')
        with patch.object(builder, 'build_staged', side_effect=stage):
            builder.build(self.output, self.root / 'downloads')
        self.assertEqual((self.output / 'verified').read_text(), 'yes')
        self.assertTrue(self.output.with_suffix('.sha256.json').is_file())
        self.assertFalse(list(self.root.glob('.deadlock-build-*')))

    def test_concurrent_output_is_not_replaced(self):
        def stage(output, *_):
            output.mkdir()
            self.output.mkdir()
            (self.output / 'other build').touch()
        with patch.object(builder, 'build_staged', side_effect=stage), self.assertRaises(SystemExit):
            builder.build(self.output, self.root / 'downloads')
        self.assertTrue((self.output / 'other build').exists())

    def test_dangling_output_symlink_is_preserved(self):
        self.output.symlink_to(self.root / 'missing')
        with patch.object(builder, 'build_staged') as build, self.assertRaises(SystemExit):
            builder.build(self.output, self.root / 'downloads')
        self.assertTrue(self.output.is_symlink())
        build.assert_not_called()


class PreviewReplacementTests(unittest.TestCase):
    setUp = PackagingTests.setUp

    def preview(self, app, version):
        (app / 'Contents/Resources').mkdir(parents=True)
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({
            'CFBundleIdentifier': 'dev.shrav-k.deadlock-manager', 'CFBundleShortVersionString': version}))
        (app / 'Contents/Resources/build-inputs.json').write_text(json.dumps({'version': version}))
        app.with_suffix('.sha256.json').write_text(json.dumps({
            str(p.relative_to(app)): builder.sha256(p) for p in app.rglob('*') if p.is_file()}))

    def version(self, app):
        return plistlib.loads((app / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString']

    def test_two_updates_leave_current_one_previous_and_receipts(self):
        self.preview(self.output, 'old')
        with patch.object(builder, 'require_closed'):
            for version in ('next', 'newest'):
                with patch.object(builder, 'build_staged', side_effect=lambda p, *_: self.preview(p, version)):
                    builder.build(self.output, self.root / 'downloads', replace=True)
        previous = self.root / 'Previous/Manager.app'
        self.assertEqual(self.version(self.output), 'newest')
        self.assertEqual(self.version(previous), 'next')
        self.assertEqual(len(list(self.root.rglob('*.app'))), 2)
        self.assertEqual(len(list((self.root / 'build-history').glob('*.json'))), 3)
        builder.verified_preview(self.output); builder.verified_preview(previous)

    def test_failed_replacement_build_leaves_current_and_rollback_untouched(self):
        previous = self.root / 'Previous/Manager.app'
        self.preview(self.output, 'current'); self.preview(previous, 'previous')
        with patch.object(builder, 'require_closed'), patch.object(builder, 'build_staged', side_effect=RuntimeError('compile')), \
                self.assertRaises(RuntimeError):
            builder.build(self.output, self.root / 'downloads', replace=True)
        self.assertEqual(self.version(self.output), 'current')
        self.assertEqual(self.version(previous), 'previous')
        self.assertFalse((self.root / '.preview-transaction').exists())

    def test_late_manifest_publication_failure_rolls_back_both_apps(self):
        previous = self.root / 'Previous/Manager.app'
        self.preview(self.output, 'current'); self.preview(previous, 'previous')
        rename = Path.rename
        def fail_manifest(path, target):
            if path.name == 'Manager.sha256.json' and path.parent.name.startswith('.deadlock-build-'):
                raise OSError('publish manifest')
            return rename(path, target)
        with patch.object(builder, 'require_closed'), \
                patch.object(builder, 'build_staged', side_effect=lambda p, *_: self.preview(p, 'new')), \
                patch.object(Path, 'rename', fail_manifest), self.assertRaisesRegex(OSError, 'publish manifest'):
            builder.build(self.output, self.root / 'downloads', replace=True)
        self.assertEqual(self.version(self.output), 'current')
        self.assertEqual(self.version(previous), 'previous')
        builder.verified_preview(self.output); builder.verified_preview(previous)
        self.assertFalse((self.root / '.preview-transaction').exists())

    def test_failed_rollback_retains_old_apps_and_blocks_another_update(self):
        previous = self.root / 'Previous/Manager.app'
        self.preview(self.output, 'current'); self.preview(previous, 'previous')
        rename = Path.rename
        def fail_output(path, target):
            if target == self.output:
                raise OSError('output unavailable')
            return rename(path, target)
        with patch.object(builder, 'require_closed'), \
                patch.object(builder, 'build_staged', side_effect=lambda p, *_: self.preview(p, 'new')), \
                patch.object(Path, 'rename', fail_output), self.assertRaisesRegex(SystemExit, 'manual recovery'):
            builder.build(self.output, self.root / 'downloads', replace=True)
        self.assertEqual(self.version(previous), 'current')
        self.assertEqual(self.version(self.root / '.preview-transaction/previous.app'), 'previous')
        with self.assertRaisesRegex(SystemExit, 'interrupted'):
            builder.replacement_inputs(self.output)

    def test_running_bundled_watcher_blocks_update_even_without_manager(self):
        self.preview(self.output, 'current')
        process = SimpleNamespace(stdout=str(self.output / 'Contents/Resources/python/bin/python3') + '\n')
        with patch.object(builder.subprocess, 'run', return_value=process), \
                patch.object(builder, 'build_staged') as build, self.assertRaisesRegex(SystemExit, 'session'):
            builder.build(self.output, self.root / 'downloads', replace=True)
        build.assert_not_called()

    def test_changed_app_or_extra_files_are_not_discarded(self):
        self.preview(self.output, 'current')
        (self.output / 'user-note').write_text('preserve')
        with patch.object(builder, 'build_staged') as build, self.assertRaisesRegex(SystemExit, 'changed'):
            builder.build(self.output, self.root / 'downloads', replace=True)
        build.assert_not_called()
        self.assertEqual((self.output / 'user-note').read_text(), 'preserve')

    def test_history_retention_protects_current_rollback_and_unrelated_files(self):
        history = self.root / 'build-history'; history.mkdir()
        for i in range(25):
            (history / f'{i}.json').write_text(json.dumps({'schema': 1, 'kind': 'deadlock-manager-preview', 'manifest_sha256': str(i)}))
        (history / 'notes.json').write_text('{}')
        builder.prune_history(history, ['0', '1'])
        self.assertEqual(len(list(history.glob('*.json'))), 21)
        self.assertTrue((history / '0.json').exists() and (history / '1.json').exists())
        self.assertTrue((history / 'notes.json').exists())
