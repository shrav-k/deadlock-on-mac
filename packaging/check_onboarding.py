#!/usr/bin/env python3
"""Exercise the packaged dependencies in an empty workspace, without Steam/game."""
import argparse
from datetime import datetime, timezone
import inspect
import json
import os
from pathlib import Path
import platform
import plistlib
import subprocess
import tempfile


def qualify_game_mode(workspace, apple_tool=None, require_xcode=None):
    """Read-only qualification; strict mode cannot pass on a cached/provided tool."""
    import plistlib
    import subprocess
    from pathlib import Path
    from deadlock_mac import game_mode
    from deadlock_mac.runtime import clean_env
    from deadlock_mac.storage import ManagerError, sha256

    workspace = Path(workspace)
    if apple_tool and require_xcode:
        raise ManagerError('An explicit tool fixture cannot qualify fresh Xcode discovery.')
    if ((workspace / 'DeadlockData/tools/game-mode').exists() or
            (workspace / 'Tools/game-mode-investigation/gamepolicyctl').exists()):
        raise ManagerError('Qualification requires a workspace without cached or legacy Game Mode tools.')
    result = {}
    expected = None
    if require_xcode:
        xcode = Path(require_xcode).resolve(strict=True)
        expected = (xcode / 'Contents/Developer/usr/bin/gamepolicyctl').resolve(strict=True)
        if not expected.is_relative_to(xcode):
            raise ManagerError('Xcode tool resolves outside the requested installation.')
        info = plistlib.loads((xcode / 'Contents/Info.plist').read_bytes())
        version = plistlib.loads((xcode / 'Contents/version.plist').read_bytes())
        if info.get('CFBundleIdentifier') != 'com.apple.dt.Xcode':
            raise ManagerError('The requested installation is not an Xcode app bundle.')
        # Xcode uses App Store / Developer ID signing, unlike the platform-signed
        # gamepolicyctl. Match Apple's Xcode identity in those distribution chains.
        requirement = ('=anchor apple generic and identifier "com.apple.dt.Xcode" and '
                       '(certificate leaf[field.1.2.840.113635.100.6.1.9] exists or '
                       '(certificate 1[field.1.2.840.113635.100.6.2.6] exists and '
                       'certificate leaf[field.1.2.840.113635.100.6.1.13] exists and '
                       'certificate leaf[subject.OU] = "59GAB85EFG"))')
        verified = subprocess.run(['/usr/bin/codesign', '--verify', '--strict', '-R', requirement, str(xcode)],
                                  env=clean_env(), capture_output=True, text=True, timeout=90)
        if verified.returncode:
            raise ManagerError('The requested Xcode installation failed Apple signature verification.')
        env = clean_env()
        env['DEVELOPER_DIR'] = str(xcode / 'Contents/Developer')
        readiness = subprocess.run(['/usr/bin/xcodebuild', '-checkFirstLaunchStatus'], env=env,
                                   capture_output=True, text=True, timeout=30)
        if readiness.returncode:
            raise ManagerError('Open Xcode to review its license and complete first-run setup before qualification.')
        original = game_mode.AppleTool(expected).status()
        result['xcode'] = {'path': str(xcode), 'version': version['CFBundleShortVersionString'],
                           'build': version['ProductBuildVersion'], 'first_launch_complete': True,
                           'apple_signature_verified': True}
    try:
        prepared = game_mode.prepare_tool(workspace)
        result['initial_game_mode_discovery'] = 'ready'
        result['initial_tool_source'] = prepared['source']
        result['tool_sha256'] = prepared['sha256']
    except ManagerError as exc:
        if require_xcode or 'Install or update Xcode' not in str(exc):
            raise
        result['initial_game_mode_discovery'] = 'missing-compatible-Apple-tool-reported'
        result['initial_game_mode_message'] = str(exc)
    if expected:
        if Path(prepared['source']).resolve() != expected or prepared['sha256'] != sha256(expected):
            raise ManagerError('Automatic discovery did not use the requested Xcode installation.')
        automatic = game_mode.prepare_tool(workspace)
        if (automatic['path'] != prepared['path'] or
                game_mode.select_tool(workspace).path != Path(prepared['path'])):
            raise ManagerError('Repeat setup did not reuse the newly verified tool.')
        final = game_mode.AppleTool(expected).status()
        if final['policy'] != original['policy'] or prepared['status']['policy'] != original['policy']:
            raise ManagerError('Game Mode policy changed during read-only qualification.')
        result.update(fresh_xcode_discovery='passed', subsequent_automatic_discovery='passed',
                      policy_unchanged=original['policy'], initial_status=original, final_status=final)
    if apple_tool:
        # This fixture does not establish fresh official-Xcode discovery.
        tool = game_mode.AppleTool(apple_tool)
        before = tool.status()['policy']
        prepared = game_mode.prepare_tool(workspace, tool.path)
        automatic = game_mode.prepare_tool(workspace)
        assert automatic['path'] == prepared['path']
        assert game_mode.select_tool(workspace).path == Path(prepared['path'])
        assert tool.status()['policy'] == before
        result.update(provided_apple_tool='signature/status/cache passed',
                      subsequent_automatic_discovery='passed', policy_unchanged=before)
    return result


def qualify_hotfix(workspace, resources):
    """Install/upgrade/rollback the bundled bytes in an empty, non-Wine workspace."""
    from pathlib import Path
    import json
    from deadlock_mac import hotfix
    from deadlock_mac.storage import atomic_json

    workspace, resources = Path(workspace), Path(resources)
    inputs = json.loads((resources / 'build-inputs.json').read_text())
    if not inputs.get('wine_hotfix'):
        return {'packaged_hotfix': 'not bundled; not qualified'}
    current, previous = hotfix.specification(), hotfix.previous_specification()
    profile = {'id': 'fresh', 'provider': 'wine', 'wine_family': 'highball',
               'runtime_version': current['runtime_version'], 'prefix': str(workspace / 'Bottles/fresh')}
    assert hotfix.install_available(workspace, profile)
    assert hotfix.status(profile)['id'] == current['id']
    assert hotfix.install_available(workspace, profile)
    assert hotfix.configure(workspace, profile, True, previous=True)['id'] == previous['id']
    assert hotfix.install_available(workspace, profile)  # Explicit rollback survives setup.
    assert hotfix.status(profile)['id'] == previous['id']
    # A legacy receipt without an explicit pin upgrades on requested setup.
    atomic_json(hotfix.receipt(workspace, profile), {'schema': 1, 'enabled': True, 'id': previous['id']})
    assert hotfix.install_available(workspace, profile)
    assert hotfix.status(profile)['id'] == current['id']
    assert not hotfix.configure(workspace, profile, False)['enabled']
    assert not hotfix.install_available(workspace, profile)
    assert hotfix.configure(workspace, profile, True)['id'] == current['id']
    assert not (workspace / 'Bottles').exists()
    return {'packaged_hotfix': 'fresh/repeat/upgrade/rollback/opt-out passed',
            'hotfix_revision': current['id'], 'rollback_revision': previous['id']}


# Executed by the app's own isolated interpreter, using only its shipped modules.
PROBE = r'''
import json, sys
from pathlib import Path
resources, workspace = map(Path, sys.argv[1:3])
options = json.loads(sys.argv[3])
sys.path.insert(0, str(resources / 'manager/src'))
from deadlock_mac import media_runtime

assert not (resources / 'manager/packaging/build_media_runtime.py').exists()
first = media_runtime.install(workspace)
assert media_runtime.install(workspace) == first
media_runtime.verify(first)
assert not (workspace / 'Downloads').exists(), 'Packaged install unexpectedly fetched/builds dependencies'
assert not (workspace / 'Bottles').exists()
result = {'packaged_media': 'passed', 'repeat_install': 'passed', 'source_checkout_required': False,
          'network_or_compiler_required': False, 'steam_or_game_started': False}
result.update(qualify_hotfix(workspace, resources))
result.update(qualify_game_mode(workspace, **options))
print(json.dumps(result))
'''


def check(app, report, apple_tool=None, require_xcode=None):
    if apple_tool and require_xcode:
        raise ValueError('--apple-tool and --require-xcode are mutually exclusive')
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
        options = {key: str(value.resolve(strict=True)) if value else None for key, value in
                   (('apple_tool', apple_tool), ('require_xcode', require_xcode))}
        probe = inspect.getsource(qualify_game_mode) + '\n' + inspect.getsource(qualify_hotfix) + '\n' + PROBE
        command = [str(python), '-I', '-B', '-c', probe, str(resources), str(workspace), json.dumps(options)]
        run = subprocess.run(command, env=env, text=True, capture_output=True, timeout=120)
        if run.returncode:
            raise SystemExit(f'Packaged onboarding check failed\n{run.stdout}\n{run.stderr}')
        result = json.loads(run.stdout)
    result.update(scope='Dependency preparation only; no full Steam installation, sign-in or gameplay',
                  temporary_workspace_removed=True, macos=platform.mac_ver()[0],
                  app_version=plistlib.loads((app / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString'],
                  checked_utc=datetime.now(timezone.utc).isoformat())
    report.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--app', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    group = p.add_mutually_exclusive_group()
    group.add_argument('--apple-tool', type=Path, help='Optional existing Apple-signed test fixture; never distributed')
    group.add_argument('--require-xcode', type=Path, help='Require fresh automatic discovery from this official Xcode app')
    a = p.parse_args()
    check(a.app, a.report.resolve(), a.apple_tool, a.require_xcode)
