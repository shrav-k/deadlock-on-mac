#!/usr/bin/env python3
"""Opt-in live MENU-ONLY launch/exit check. Never enters gameplay or sends input.

Uses an already installed, signed-in profile. Never downloads a second game,
changes settings, force-kills processes, or automates Steam account prompts.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from deadlock_mac import game_session
from deadlock_mac.cli import load_profile, timestamp
from deadlock_mac.game_mode import AppleTool
from deadlock_mac.runtime import clean_env
from deadlock_mac.storage import ManagerError, atomic_json, private_dir


def check(workspace, profile_id, tool_path, cycles, settle_seconds=15, manager=None,
          steam_only=False, idle_seconds=180):
    workspace = workspace.resolve()
    profile = load_profile(workspace, profile_id)
    if game_session.games_in_prefix(profile['prefix']):
        raise ManagerError('Close Deadlock before starting this menu-only lifecycle check.')
    if game_session.status().get('restore_pending'):
        raise ManagerError('Finish or recover the existing Game Mode session before testing.')
    if not 1 <= cycles <= 10 or not 5 <= settle_seconds <= 60:
        raise ManagerError('Use 1–10 cycles and 5–60 seconds of menu settling time.')
    if not 0 <= idle_seconds <= 600:
        raise ManagerError('Use 0–600 seconds of Steam idle time.')
    tool = AppleTool(tool_path)
    tool_path = tool.path
    original = tool.status()['policy']
    folder = private_dir(workspace / 'DeadlockData/lifecycle-checks' / timestamp())
    result = {'schema': 1, 'scope': 'Steam-only lifecycle; no game launch' if steam_only else 'menu-only lifecycle; no gameplay or display acceptance',
              'original_policy': original, 'cycles': [], 'passed': False}
    if manager:
        resources = manager.resolve() / 'Contents/Resources'
        cli = [str(resources / 'python/bin/python3'), '-I', '-B', '-u', str(resources / 'launcher.py')]
    else:
        cli = [sys.executable, '-I', '-B', '-u', str(REPO / 'bin/deadlock-mac')]
    cli += ['--workspace', str(workspace), '--profile', profile_id]

    def command(*arguments):
        response = subprocess.run([*cli, *arguments], env=clean_env(), stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True, timeout=150)
        with (folder / 'commands.log').open('a') as stream:
            stream.write(json.dumps(list(arguments)) + '\n' + response.stdout + response.stderr)
        (folder / 'commands.log').chmod(0o600)
        if response.returncode:
            raise ManagerError(f'{arguments[0]} failed; inspect {folder / "commands.log"}')
        return response.stdout

    try:
        for index in range(cycles):
            cycle = {'number': index + 1, 'started_utc': datetime.now(timezone.utc).isoformat()}
            result['cycles'].append(cycle)
            print(f'{"Steam-only" if steam_only else "Menu-only"} lifecycle cycle {index + 1}/{cycles}', flush=True)
            if steam_only:
                command('steam')
                deadline = time.monotonic() + 180
                while not (game_session.processes_in_prefix(profile['prefix'], 'steam.exe')
                           and game_session.processes_in_prefix(profile['prefix'], 'steamwebhelper.exe')):
                    if time.monotonic() >= deadline:
                        raise ManagerError('Steam client and browser helper did not appear; inspect Steam before retrying.')
                    time.sleep(1)
                print(f'Client and browser processes present; idling {idle_seconds}s before shutdown (not UI acceptance).', flush=True)
                idle_until = time.monotonic() + idle_seconds
                while time.monotonic() < idle_until:
                    if game_session.games_in_prefix(profile['prefix']):
                        raise ManagerError('Deadlock started during the Steam-only test. Stopping the check without closing the game.')
                    time.sleep(max(0, min(1, idle_until - time.monotonic())))
                if game_session.games_in_prefix(profile['prefix']):
                    raise ManagerError('Deadlock started during the Steam-only test. Stopping the check without closing the game.')
                clients = game_session.processes_in_prefix(profile['prefix'], 'steam.exe')
                if len(clients) != 1:
                    raise ManagerError('Expected one Steam client before shutdown.')
                cycle['steam_pid'] = next(iter(clients))
                cycle['idle_seconds'] = idle_seconds
                print('Requesting normal Steam shutdown…', flush=True)
                started = time.monotonic()
                cycle['steam_exit_result'] = command('steam-exit')
                cycle['steam_exit_seconds'] = round(time.monotonic() - started, 2)
                if tool.status()['policy'] != original:
                    raise ManagerError('Game Mode policy changed during a Steam-only check.')
                command('steam-exit')
                cycle['passed'] = True
                atomic_json(folder / 'report.json', result)
                continue
            command('launch', '--game-mode-tool', str(tool_path))
            deadline = time.monotonic() + 180
            while not game_session.games_in_prefix(profile['prefix']):
                state = game_session.status()
                if state.get('phase') == 'finished' or time.monotonic() >= deadline:
                    raise ManagerError('The game did not stay running after launch.')
                time.sleep(1)
            time.sleep(settle_seconds)
            games = game_session.games_in_prefix(profile['prefix'])
            if len(games) != 1 or tool.status()['policy'] != 'on':
                raise ManagerError('Expected one running game and Game Mode On before Exit.')
            cycle['game_pid'] = next(iter(games))
            started = time.monotonic()
            cycle['exit_result'] = command('exit')
            cycle['exit_seconds'] = round(time.monotonic() - started, 2)
            if game_session.games_in_prefix(profile['prefix']) or tool.status()['policy'] != original:
                raise ManagerError('Actual game exit or previous Game Mode policy was not verified.')
            cycle['restored_policy'] = original
            if not game_session.processes_in_prefix(profile['prefix'], 'steam.exe'):
                raise ManagerError('Game Exit unexpectedly closed Windows Steam.')
            command('exit')  # Idempotence: must not start another game/client.
            # Cold Steam startup on the next cycle; verify both shutdown and no-op.
            cycle['steam_exit_result'] = command('steam-exit')
            command('steam-exit')
            cycle['passed'] = True
            atomic_json(folder / 'report.json', result)
        result['passed'] = True
    except (ManagerError, OSError, subprocess.SubprocessError) as exc:
        result['error'] = str(exc)
        # Attempt normal closure only. Preserve the original failure and recovery state.
        if not steam_only:
            try:
                result['cleanup'] = command('exit')
            except (ManagerError, OSError, subprocess.SubprocessError) as cleanup:
                result['cleanup_error'] = str(cleanup)
        raise
    finally:
        result['finished_utc'] = datetime.now(timezone.utc).isoformat()
        atomic_json(folder / 'report.json', result)
        print(f'Report: {folder / "report.json"}', flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--profile', default='highball')
    parser.add_argument('--game-mode-tool', type=Path, required=True)
    parser.add_argument('--manager-app', type=Path, help='Test this built app’s bundled CLI instead of source')
    parser.add_argument('--cycles', type=int, default=1)
    parser.add_argument('--settle-seconds', type=int, default=15)
    parser.add_argument('--steam-only', action='store_true', help='Open and close Steam without launching Deadlock')
    parser.add_argument('--idle-seconds', type=int, default=180, help='Steam-only idle interval before shutdown (0–600)')
    args = parser.parse_args()
    try:
        check(args.workspace, args.profile, args.game_mode_tool, args.cycles, args.settle_seconds,
              args.manager_app, args.steam_only, args.idle_seconds)
    except (ManagerError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Lifecycle check failed: {exc}\n')
