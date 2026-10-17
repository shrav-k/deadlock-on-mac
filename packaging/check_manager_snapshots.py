#!/usr/bin/env python3
"""Render synthetic manager fixtures. Never captures the user's desktop or games.

Use a new private output folder, inspect its PNGs, and retain the manifest/source
revision with the review. Images are evidence for review, not automatic approval
of appearance or substitutes for actual button tests.
"""
import argparse
from pathlib import Path
import platform
import plistlib
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='deadlock-snapshots-') as temporary:
        app = Path(temporary) / 'ManagerSnapshots.app'
        binary = app / 'Contents/MacOS/ManagerSnapshots'
        binary.parent.mkdir(parents=True)
        with (app / 'Contents/Info.plist').open('wb') as stream:
            plistlib.dump({'CFBundleExecutable': binary.name, 'CFBundlePackageType': 'APPL',
                          'CFBundleIdentifier': 'dev.shrav-k.deadlock-manager.snapshot-tests'}, stream)
        subprocess.run(['/usr/bin/xcrun', 'swiftc', '-parse-as-library', '-D', 'MANAGER_APP_TESTS',
                        '-target', f'{platform.machine()}-apple-macos15.0',
                        str(REPO / 'packaging/ManagerLifecycle.swift'),
                        str(REPO / 'packaging/WineActivation.swift'),
                        str(REPO / 'packaging/VisualTesting.swift'), str(REPO / 'packaging/DeadlockManager.swift'),
                        str(REPO / 'tests/native/manager_snapshot_test.swift'), '-o', str(binary)], check=True)
        subprocess.run([str(binary), str(output)], check=True, timeout=60)
    print(output)


if __name__ == '__main__':
    main()
