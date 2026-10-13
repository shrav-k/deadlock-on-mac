"""Fault injection for app publication; no downloads, signing or GUI required."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
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
