#!/usr/bin/env python3
"""Check the owned helper's close protocol in real Wine, with no window or game."""
import argparse
from pathlib import Path
import subprocess
import sys
import threading

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from deadlock_mac import display_test, displays
from deadlock_mac.backup import wine_processes_running
from deadlock_mac.cli import load_profile
from deadlock_mac.game_session import processes_in_prefix
from deadlock_mac.runtime import environment, validate_profile, wine_binary
from deadlock_mac.storage import ManagerError, atomic_json, sha256


def check(workspace, name):
    profile = load_profile(workspace, name)
    validate_profile(profile, workspace)
    displays.require_supported(profile)
    if wine_processes_running():
        raise ManagerError('Close all Wine sessions before this no-window check.')
    env = environment(profile)
    stopped = threading.Event()
    events = []
    def report(line):
        events.append(line)
        print(line, flush=True)
        if line == 'control_check=ready':
            stopped.set()
    deadline = threading.Timer(45, stopped.set)
    deadline.start()
    try:
        result = display_test.run([str(wine_binary(profile)), str(displays.helper('wine-displays.exe')),
                                   '--check-control'], env=env, cwd=profile['prefix'], stopped=stopped, report=report)
        if result.returncode or 'control_check=parent_closed' not in result.stdout:
            raise ManagerError('Wine control-pipe check failed: ' + result.stdout[-2000:])
    finally:
        deadline.cancel()
        if any(processes_in_prefix(profile['prefix'], executable) for executable in ('steam.exe', 'deadlock.exe')):
            raise ManagerError('Steam/game started during the check; its session was left running.')
        subprocess.run([str(wine_binary(profile)), 'wineboot', '-e', '-s'], env=env,
                       cwd=profile['prefix'], capture_output=True, timeout=20, check=True)
        subprocess.run([str(Path(profile['runtime']) / 'bin/wineserver'), '-w'], env=env,
                       capture_output=True, timeout=20, check=True)
    atomic_json(workspace / 'DeadlockData/display-tests' / name / 'control-latest.json',
                {'window_created': False, 'game_launched': False, 'runtime_version': profile['runtime_version'],
                 'helper_sha256': sha256(displays.helper('wine-displays.exe')),
                 'returncode': result.returncode, 'events': events})
    print('PASS actual Wine control pipe closed normally; no window or game created.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--profile', default='highball')
    args = parser.parse_args()
    check(args.workspace.expanduser().resolve(), args.profile)
