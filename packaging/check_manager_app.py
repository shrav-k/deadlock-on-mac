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
WORKER = r'''import pathlib, subprocess, sys, time
from deadlock_mac.diagnostic_control import cancellation
root = pathlib.Path(sys.argv[sys.argv.index('--workspace') + 1])
if sys.argv[-2:] == ['game-mode', '--session']:
    fixture = root / 'session-fixture.json'
    print(fixture.read_text() if fixture.exists() else '{"phase":"idle"}')
    sys.exit(0)
if '--manager-control-stdin' in sys.argv:
    with cancellation(sys.stdin) as stopped:
        # A real descendant is essential: Foundation Process.terminate used to
        # terminate the helper too, bypassing its pipe-driven cleanup.
        child = subprocess.Popen([sys.executable, '-c',
            "import signal,sys; signal.signal(signal.SIGTERM, lambda *_: sys.exit(71)); "
            "sys.stdin.read(); print('child closed through pipe', flush=True)"], stdin=subprocess.PIPE)
        print('worker started', flush=True)
        if not stopped.wait(5):
            child.kill()
            sys.exit(72)
        child.stdin.close()
        if child.wait(timeout=2) != 0:
            sys.exit(73)
        (root / 'worker-finished').write_text('restored')
else:
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
        (resources / 'launcher.py').write_text('import sys; sys.path.insert(0, ' + repr(str(REPO / 'src')) + ')\n' + WORKER)
        with (app / 'Contents/Info.plist').open('wb') as stream:
            plistlib.dump({'CFBundleExecutable': binary.name, 'CFBundlePackageType': 'APPL',
                          'CFBundleIdentifier': 'dev.shrav-k.deadlock-manager.integration-tests'}, stream)
        subprocess.run(['/usr/bin/xcrun', 'swiftc', '-parse-as-library', '-D', 'MANAGER_APP_TESTS',
                        '-target', f'{platform.machine()}-apple-macos15.0',
                        str(REPO / 'packaging/ManagerLifecycle.swift'),
                        str(REPO / 'packaging/WineActivation.swift'),
                        str(REPO / 'packaging/DeadlockManager.swift'),
                        str(REPO / 'tests/native/manager_app_test.swift'), '-o', str(binary)], check=True)
        for scenario in ('idle-close', 'success-close', 'success-quit', 'failure-close',
                         'failure-quit', 'failure-close-retry-quit', 'diagnostic-close',
                         'diagnostic-quit', 'diagnostic-before-spawn', 'grid-close', 'grid-quit', 'grid-before-spawn', 'grid-stop'):
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
                        '-target', f'{platform.machine()}-apple-macos15.0',
                        str(REPO / 'packaging/ManagerLifecycle.swift'),
                        str(REPO / 'packaging/WineActivation.swift'),
                        str(REPO / 'packaging/DeadlockManager.swift'),
                        str(REPO / 'tests/native/display_model_test.swift'), '-o', str(display_test)], check=True)
        subprocess.run([str(display_test)], check=True, timeout=10)
        activation_test = root / 'ActivationTests'
        subprocess.run(['/usr/bin/xcrun', 'swiftc', '-parse-as-library',
                        '-target', f'{platform.machine()}-apple-macos15.0',
                        str(REPO / 'packaging/WineActivation.swift'),
                        str(REPO / 'tests/native/wine_activation_test.swift'), '-o', str(activation_test)], check=True)
        subprocess.run([str(activation_test)], check=True, timeout=10)
        session_test = root / 'SessionReaderTests'
        subprocess.run(['/usr/bin/xcrun', 'swiftc', '-parse-as-library', '-D', 'MANAGER_APP_TESTS',
                        '-target', f'{platform.machine()}-apple-macos15.0',
                        str(REPO / 'packaging/ManagerLifecycle.swift'),
                        str(REPO / 'packaging/WineActivation.swift'),
                        str(REPO / 'packaging/DeadlockManager.swift'),
                        str(REPO / 'tests/native/session_reader_test.swift'), '-o', str(session_test)], check=True)
        subprocess.run([str(session_test), str(resources), str(root)], check=True, timeout=20)


if __name__ == '__main__':
    main()
