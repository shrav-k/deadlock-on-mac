#!/usr/bin/env python3
"""Opt-in WinMM startup/conversion probe, with Steam and all Wine sessions closed.

Does not mute Steam, modify the prefix, record a microphone or launch a game.
--candidate is an explicit experiment: a hash manifest is required, and the
overlay applies only to these child processes. The installed engine is retained.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from deadlock_mac.backup import wine_processes_running
from deadlock_mac.cli import load_profile, timestamp
from deadlock_mac.game_exit import wait_for_wine_shutdown
from deadlock_mac.hotfix import verify
from deadlock_mac.runtime import environment, wine_binary
from deadlock_mac.storage import ManagerError, atomic_json, private_dir, sha256


def candidate_environment(profile, candidate, manifest):
    env = environment(profile)
    if candidate is None:
        if manifest is not None:
            raise ManagerError('A candidate manifest requires a candidate directory.')
        return env, None
    if manifest is None:
        raise ManagerError('An explicit candidate hash manifest is required.')
    if profile.get('wine_family') != 'highball':
        raise ManagerError('This candidate lane requires the matched Highball loader.')
    files = json.loads(manifest.read_text())
    expected = {'x86_64-windows/winmm.dll', 'i386-windows/winmm.dll'}
    if not isinstance(files, dict) or set(files) != expected or any(
            not isinstance(value, str) or len(value) != 64 or
            any(char not in '0123456789abcdef' for char in value) for value in files.values()):
        raise ManagerError('Candidate manifest must contain exactly the two WinMM SHA-256 digests.')
    directory = verify(candidate, {'files': files})
    env['WINEDLLPATH_PREPEND'] = str(directory) + ':' + env['WINEDLLPATH_PREPEND']
    return env, files


def check(workspace, compiler, profile_id, candidate=None, manifest=None, enumerate_only=False):
    if wine_processes_running():
        raise ManagerError('Close Steam, Deadlock and every Wine session before audio qualification.')
    profile = load_profile(workspace, profile_id)
    if profile.get('provider') != 'wine':
        raise ManagerError('Audio qualification requires a Wine profile.')
    env, files = candidate_environment(profile, candidate, manifest)
    root = private_dir(workspace / 'DeadlockData/audio-checks' / timestamp())
    source = REPO / 'tests/native/winmm_probe.c'
    report = {'schema': 1, 'profile': profile_id, 'runtime': profile['runtime_version'],
              'candidate_files': files, 'probe_source_sha256': sha256(source), 'tests': [], 'passed': False,
              'scope': 'WinMM enumeration, output format conversion and silent playback; no audible-quality or gameplay acceptance'}
    try:
        for arch, executable in (('x86_64', 'x86_64-w64-mingw32-clang'), ('i386', 'i686-w64-mingw32-clang')):
            probe = root / ('winmm-' + arch + '.exe')
            subprocess.run([str(compiler / executable), '-Wall', '-Wextra', '-Werror', '-O2',
                            str(source), '-lwinmm', '-o', str(probe)], check=True, timeout=60)
            args = [str(wine_binary(profile)), str(probe)]
            if enumerate_only:
                args.append('--enumerate-only')
            print(f'WinMM {arch}: {"enumeration" if enumerate_only else "enumeration and 23 silent output formats"}', flush=True)
            result = {'architecture': arch, 'probe_sha256': sha256(probe), 'passed': False}
            report['tests'].append(result)
            with (root / (arch + '.log')).open('xb') as stream:
                try:
                    run = subprocess.run(args, env=env, cwd=root, stdin=subprocess.DEVNULL,
                                         stdout=stream, stderr=subprocess.STDOUT, timeout=65)
                except subprocess.TimeoutExpired:
                    result['error'] = 'Outer timeout; the probe did not complete. Inspect owned processes before another run.'
                    raise ManagerError(result['error'])
            output = (root / (arch + '.log')).read_text(errors='replace')
            result.update(exit_code=run.returncode, passed=run.returncode == 0 and 'failures=0' in output)
            wait_for_wine_shutdown(profile)
            if not result['passed']:
                raise ManagerError(f'WinMM {arch} failed; preserve {root} before testing another variant.')
        report['passed'] = True
    except (ManagerError, OSError, ValueError, subprocess.SubprocessError) as error:
        report['error'] = str(error)
        raise
    finally:
        atomic_json(root / 'report.json', report)
        print(f'Audio report: {root / "report.json"}', flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--profile', default='highball')
    parser.add_argument('--compiler-bin', type=Path, required=True)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--candidate-manifest', type=Path)
    parser.add_argument('--enumerate-only', action='store_true')
    args = parser.parse_args()
    try:
        check(args.workspace.resolve(), args.compiler_bin.resolve(), args.profile,
              args.candidate.resolve() if args.candidate else None, args.candidate_manifest, args.enumerate_only)
    except (ManagerError, OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f'Audio qualification failed: {error}\n')
