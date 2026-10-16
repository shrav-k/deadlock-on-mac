#!/usr/bin/env python3
"""Exercise the packaged dependencies in an empty workspace, without Steam/game."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


# Executed by the app's own isolated interpreter, using only its shipped modules.
PROBE = r'''
import json, sys
from pathlib import Path
resources, workspace = map(Path, sys.argv[1:3])
sys.path.insert(0, str(resources / 'manager/src'))
from deadlock_mac import game_mode, media_runtime
from deadlock_mac.storage import ManagerError

assert not (resources / 'manager/packaging/build_media_runtime.py').exists()
first = media_runtime.install(workspace)
assert media_runtime.install(workspace) == first
media_runtime.verify(first)
assert not (workspace / 'Downloads').exists(), 'Packaged install unexpectedly fetched/builds dependencies'
assert not (workspace / 'Bottles').exists()
result = {'packaged_media': 'passed', 'repeat_install': 'passed', 'source_checkout_required': False,
          'network_or_compiler_required': False, 'steam_or_game_started': False}
try:
    prepared = game_mode.prepare_tool(workspace)
    result['initial_game_mode_discovery'] = 'ready'
except ManagerError as exc:
    if 'Install or update Xcode' not in str(exc): raise
    result['initial_game_mode_discovery'] = 'missing-compatible-Apple-tool-reported'
    result['initial_game_mode_message'] = str(exc)
if len(sys.argv) == 4:
    # An explicitly supplied Apple-signed test fixture exercises the real cache.
    # It is not evidence of zero-prerequisite discovery on a fresh Mac.
    tool = game_mode.AppleTool(sys.argv[3])
    before = tool.status()['policy']
    prepared = game_mode.prepare_tool(workspace, tool.path)
    automatic = game_mode.prepare_tool(workspace)
    assert automatic['path'] == prepared['path']
    assert game_mode.select_tool(workspace).path == Path(prepared['path'])
    assert tool.status()['policy'] == before
    result.update(provided_apple_tool='signature/status/cache passed',
                  subsequent_automatic_discovery='passed', policy_unchanged=before)
print(json.dumps(result))
'''


def check(app, report, apple_tool=None):
    app = app.resolve(strict=True)
    resources = app / 'Contents/Resources'
    python = resources / 'python/bin/python3'
    env = {k: os.environ[k] for k in ('HOME', 'USER', 'LOGNAME', 'TMPDIR') if k in os.environ}
    env['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], env=env, check=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.onboarding-check-', dir=report.parent) as temporary:
        workspace = Path(temporary).resolve() / 'empty-workspace'
        workspace.mkdir()
        command = [str(python), '-I', '-B', '-c', PROBE, str(resources), str(workspace)]
        if apple_tool: command.append(str(apple_tool.resolve(strict=True)))
        run = subprocess.run(command, env=env, text=True, capture_output=True, timeout=120)
        if run.returncode:
            raise SystemExit(f'Packaged onboarding check failed\n{run.stdout}\n{run.stderr}')
        result = json.loads(run.stdout)
    result.update(scope='Dependency preparation only; no full Steam installation, sign-in or gameplay',
                  temporary_workspace_removed=True)
    report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--app', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--apple-tool', type=Path, help='Optional existing Apple-signed test fixture; never distributed')
    a = p.parse_args()
    check(a.app, a.report.resolve(), a.apple_tool)
