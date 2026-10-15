#!/usr/bin/env python3
"""Test native app shutdown against isolated fake workers, without Wine or gameplay."""
import os
import platform
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
WORKER = '''import pathlib, signal, sys, time
root = pathlib.Path(sys.argv[sys.argv.index('--workspace') + 1])
def restored(*unused):
    (root / 'worker-finished').write_text('restored')
    print('worker cleanup complete', flush=True)
    sys.exit(0)
signal.signal(signal.SIGTERM, restored)
print('worker started', flush=True)
time.sleep(1.2)
(root / 'worker-finished').write_text('success')
print('worker cleanup complete', flush=True)
sys.exit(9 if sys.argv[-1] == 'failure' else 0)
'''


def main():
    if sys.platform != 'darwin':
        raise SystemExit('Native AppKit integration checks require macOS.')
    with tempfile.TemporaryDirectory(prefix='deadlock-app-test-') as temporary:
        root = Path(temporary)
        app = root / 'Test Manager.app'
        resources = app / 'Contents/Resources'
        binary = app / 'Contents/MacOS/ManagerAppTests'
        binary.parent.mkdir(parents=True)
        (resources / 'python/bin').mkdir(parents=True)
        (resources / 'python/bin/python3').symlink_to(Path(sys.executable).resolve())
        (resources / 'launcher.py').write_text(WORKER)
        with (app / 'Contents/Info.plist').open('wb') as stream:
            plistlib.dump({'CFBundleExecutable': binary.name, 'CFBundlePackageType': 'APPL',
                          'CFBundleIdentifier': 'dev.shrav-k.deadlock-manager.integration-tests'}, stream)
        subprocess.run(['/usr/bin/xcrun', 'swiftc', '-parse-as-library', '-D', 'MANAGER_APP_TESTS',
                        '-target', f'{platform.machine()}-apple-macos15.0',
                        str(REPO / 'packaging/ManagerLifecycle.swift'),
                        str(REPO / 'packaging/DeadlockManager.swift'),
                        str(REPO / 'tests/native/manager_app_test.swift'), '-o', str(binary)], check=True)
        for scenario in ('idle-close', 'success-close', 'success-quit', 'failure-close',
                         'failure-quit', 'failure-close-retry-quit', 'diagnostic-close',
                         'diagnostic-quit', 'diagnostic-before-spawn'):
            workspace = root / scenario
            workspace.mkdir()
            env = dict(os.environ, NSUnbufferedIO='YES')
            result = subprocess.run([str(binary), scenario, str(workspace)], env=env,
                                    capture_output=True, text=True, timeout=12)
            if result.returncode or f'PASS {scenario}' not in result.stdout:
                raise SystemExit(f'{scenario} failed ({result.returncode})\n{result.stdout}\n{result.stderr}')
            print(result.stdout.strip())
        display_test = root / 'DisplayModelTests'
        subprocess.run(['/usr/bin/xcrun', 'swiftc', '-parse-as-library', '-D', 'MANAGER_APP_TESTS',
                        str(REPO / 'packaging/ManagerLifecycle.swift'),
                        str(REPO / 'packaging/DeadlockManager.swift'),
                        str(REPO / 'tests/native/display_model_test.swift'), '-o', str(display_test)], check=True)
        subprocess.run([str(display_test)], check=True, timeout=10)


if __name__ == '__main__':
    main()
