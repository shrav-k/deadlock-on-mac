"""Opt-in display preparation. Host identity and guest coordinates stay separate.

Only a closed, dedicated Wine bottle is edited. Display/scale changes invalidate
preparation; Play never silently guesses another monitor or rewrites live files.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

from . import game_settings, wine_display
from .games import require_deadlock, for_profile, from_receipt, binding, settings_adapter
from .backup import wine_processes_running
from .catalog import REPO
from .runtime import clean_env, environment, steam_path, wine_binary
from .storage import ManagerError, atomic_json, identifier, no_symlinks, private_dir, sha256


def helper(name):
    root = REPO / 'native-bin'
    if not (root / 'receipt.json').is_file():
        raise ManagerError('Display helpers are missing. Use the packaged manager, or run packaging/build_display_tools.py --downloads ../Downloads.')
    receipt = json.loads(no_symlinks(root / 'receipt.json').read_text())
    path = no_symlinks(root / name)
    if receipt.get('schema') != 1 or receipt.get('files', {}).get(name) != sha256(path):
        raise ManagerError('Display helper verification failed. Rebuild/reinstall the manager.')
    return path


def host_inventory():
    result = subprocess.run([str(helper('host-displays'))], capture_output=True, text=True,
                            timeout=15, check=True, env=clean_env())
    displays = json.loads(result.stdout)['displays']
    if not displays or len(displays) > 32 or len({d['id'] for d in displays}) != len(displays):
        raise ManagerError('Connected displays do not have unambiguous identities.')
    if sum(bool(d['main']) for d in displays) != 1 or any(d['mirrored'] for d in displays):
        raise ManagerError('Use extended displays, not mirroring, for display selection.')
    return displays


def topology(displays):
    # Session IDs and list order can change on reconnect. UUID, geometry, scale,
    # main-display role and mode are required to remain stable for preparation.
    keys = ('id', 'quartz_bounds', 'appkit_backing_scale', 'main', 'builtin', 'mode_pixels', 'mode_logical', 'refresh_hz')
    stable = sorted([{key: d[key] for key in keys} for d in displays], key=lambda d: d['id'])
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def select(displays, choice):
    if choice == 'default':
        candidates = [d for d in displays if d['main']]
    elif choice == 'external':
        candidates = [d for d in displays if not d['builtin']]
        if not candidates:
            raise ManagerError('No external display is connected. Choose a connected display and prepare it.')
    else:
        candidates = [d for d in displays if d['id'] == choice]
    if len(candidates) != 1:
        raise ManagerError('The selected display is missing or ambiguous. Refresh displays and choose one explicitly.')
    return candidates[0]


def guest_displays(output):
    if 'inventory_collected=yes visual_placement_verified=no game_selection_verified=no' not in output:
        raise ManagerError('Wine display inventory was incomplete; no monitor index was accepted.')
    matches = re.findall(r'^sdl index=(\d+) instance=\d+ primary=([01]) name=(.*?) device=(.*?) bounds=(-?\d+),(-?\d+),(\d+),(\d+)\r?$', output, re.M)
    entries = [{'index': int(i), 'main': primary == '1', 'name': name, 'device': device,
                'bounds': list(map(int, (x, y, w, h)))} for i, primary, name, device, x, y, w, h in matches]
    if not entries or len(entries) > 32 or sorted(d['index'] for d in entries) != list(range(len(entries))):
        raise ManagerError('Invalid or duplicate SDL monitor indices.')
    return entries


def match_guest(host, guests, retina):
    factor = 2 if retina else 1
    expected = [round(value * factor) for value in host['quartz_bounds']]
    matches = [g for g in guests if g['bounds'] == expected and g['main'] == host['main']]
    if len(matches) != 1:
        raise ManagerError('Wine coordinates do not match the selected host display. No index was guessed.')
    return matches[0]


def sdl_path(profile):
    require_deadlock(profile, "SDL display mapping")
    return settings_adapter(profile).sdl_path(profile)


def state_path(workspace, profile):
    return Path(workspace) / 'DeadlockData/display-selection' / (identifier(profile['id']) + '.json')


def load(workspace, profile):
    path = state_path(workspace, profile)
    if not path.exists():
        return None
    value = json.loads(no_symlinks(path).read_text())
    if value.get('schema') != 1 or value.get('profile') != profile['id'] or from_receipt(value) != for_profile(profile):
        raise ManagerError('Invalid saved display selection.')
    return value


def status(workspace, profile):
    return {'displays': host_inventory(), 'selection': load(workspace, profile)}


def require_supported(profile):
    require_deadlock(profile, "Display preparation")
    if profile.get('runtime_version') != 'highball-wine-20261006' or profile.get('provider') != 'wine':
        raise ManagerError('Display preparation currently supports the qualified Highball Wine runtime only.')


def probe(profile, *, window_index=None, allow_running=False, stopped=None, report=print,
          capture=lambda line: None, presentation='popup'):
    """Start only a diagnostic in an otherwise closed bottle and end it normally."""
    from .game_session import processes_in_prefix
    running = wine_processes_running()
    if running and (not allow_running or window_index is not None):
        raise ManagerError('Exit Windows Steam and all Wine bottles before display preparation/testing.')
    if running and not any(processes_in_prefix(profile['prefix'], name) for name in ('steam.exe', for_profile(profile).process_name)):
        raise ManagerError('Another Wine session is active. Close it before checking this display selection.')
    env = environment(profile)
    env['WINEDEBUG'] = '-all,err+all'
    if window_index is not None:
        env['MTL_HUD_ENABLED'] = '1'
    command = [str(wine_binary(profile)), str(helper('wine-displays.exe')),
               'Z:' + str(sdl_path(profile)).replace('/', '\\')]
    if window_index is not None:
        command += ['--window-index', str(window_index)]
        if presentation == 'sdl-desktop':
            command += ['--sdl-desktop']
        elif presentation != 'popup':
            raise ManagerError('Unknown display test presentation.')
    try:
        if window_index is not None:
            from .display_test import run
            result = run(command, env=env, cwd=profile['prefix'], stopped=stopped, report=report, capture=capture)
        else:
            result = subprocess.run(command, env=env, cwd=profile['prefix'], capture_output=True,
                                    text=True, timeout=45)
    finally:
        # Never stop a Steam/game that appeared during the diagnostic. wineboot
        # requests normal session shutdown, not a wineserver kill.
        if not running:
            if any(processes_in_prefix(profile['prefix'], name) for name in ('steam.exe', for_profile(profile).process_name)):
                raise ManagerError('Steam or Deadlock started during the display check. Close them before retrying.')
            subprocess.run([str(wine_binary(profile)), 'wineboot', '-e', '-s'], env=env,
                           cwd=profile['prefix'], capture_output=True, timeout=20, check=True)
            subprocess.run([str(Path(profile['runtime']) / 'bin/wineserver'), '-w'], env=env,
                           capture_output=True, timeout=20, check=True)
    if result.returncode:
        raise ManagerError(f'Display diagnostic failed (code {result.returncode}): ' + (result.stdout + result.stderr)[-2000:])
    return result.stdout


def prepare(workspace, profile, choice, retina='auto', report=print):
    require_supported(profile)
    if wine_processes_running():
        raise ManagerError('Exit Windows Steam and all Wine bottles before preparing a display.')
    if retina not in ('auto', 'on', 'off'):
        raise ManagerError('Choose automatic, on or off Retina scaling.')
    hosts = host_inventory()
    target = select(hosts, choice)
    enabled = target['appkit_backing_scale'] > 1 if retina == 'auto' else retina == 'on'
    # Validate the game schema before any registry edit.
    if 'setting.monitor_index' not in game_settings.plan(profile)[2]:
        raise ManagerError('This game configuration has no supported monitor selector.')
    sdl = sdl_path(profile)
    state = {'schema': 1, **binding(for_profile(profile)), 'profile': profile['id'], 'choice': choice, 'retina_policy': retina,
             'target_id': target['id'], 'target_name': target['name'], 'phase': 'preparing'}
    atomic_json(state_path(workspace, profile), state)
    edit = None
    try:
        edit = wine_display.configure(workspace, profile, 'on' if enabled else 'off', apply=True)
        report(f"Preparing {target['name']}; Retina {'on' if enabled else 'off'}. Checking Wine/SDL coordinates…")
        output = probe(profile)
        guests = guest_displays(output)
        if len(guests) != len(hosts) or topology(host_inventory()) != topology(hosts):
            raise ManagerError('Displays changed during preparation. Refresh and retry.')
        # Validate the entire mixed-DPI layout, not just an index or name match.
        for host in hosts:
            match_guest(host, guests, enabled)
        guest = match_guest(target, guests, enabled)
        width, height = guest['bounds'][2:]
        graphics = game_settings.configure(workspace, profile, apply=True, mode='borderless',
                                           width=width, height=height, monitor_index=guest['index'])
        state.update(phase='ready', topology=topology(hosts), retina_enabled=enabled,
                     runtime_version=profile['runtime_version'], dxmt_version=profile.get('dxmt_version'),
                     sdl_sha256=sha256(sdl), guest=guest,
                     settings={key: change['after'] for key, change in graphics['changes'].items()},
                     graphics_backup=graphics['backup'], retina_backup=edit.get('backup_id'))
        atomic_json(state_path(workspace, profile), state)
        report(f"Prepared {target['name']}: {width}×{height} borderless, SDL monitor {guest['index']}. Main display unchanged. Verify coverage, HUD size and pointer alignment in the menu.")
        return state
    except BaseException as exc:
        state.update(phase='failed', error=str(exc))
        if edit and edit.get('applied'):
            try:
                wine_display.configure(workspace, profile, apply=True, restore=edit['backup_id'])
                state['retina_rolled_back'] = True
            except Exception as rollback:
                state['retina_rollback_error'] = str(rollback)
        atomic_json(state_path(workspace, profile), state)
        raise


def validate_launch(workspace, profile, *, live=True):
    state = load(workspace, profile)
    if not state or state.get('phase') == 'unmanaged':
        return None
    require_supported(profile)
    if state.get('phase') != 'ready':
        raise ManagerError('Display preparation did not finish. Close Steam, then prepare the display again.')
    hosts = host_inventory()
    target = select(hosts, state['choice'])
    if target['id'] != state['target_id'] or topology(hosts) != state['topology']:
        raise ManagerError('Display arrangement, resolution or refresh rate changed. Exit Windows Steam and prepare the display again.')
    if (wine_display.status(profile)['enabled'] != state['retina_enabled'] or
            profile.get('runtime_version') != state['runtime_version'] or profile.get('dxmt_version') != state.get('dxmt_version') or
            sha256(sdl_path(profile)) != state['sdl_sha256']):
        raise ManagerError('Runtime, game SDL or Retina setting changed. Exit Windows Steam and prepare the display again.')
    video = game_settings.plan(profile)[2]
    if any(video.get(key) != value for key, value in state['settings'].items()):
        raise ManagerError('Game display settings changed, possibly after Steam sync. Exit Windows Steam and prepare the display again.')
    if live:
        guests = guest_displays(probe(profile, allow_running=True))
        guest = match_guest(target, guests, state['retina_enabled'])
        if (len(guests) != len(hosts) or guest['index'] != state['guest']['index'] or
                topology(host_inventory()) != state['topology']):
            raise ManagerError('Wine monitor mapping changed after reconnect. Exit Windows Steam and prepare the display again.')
    return state


def clear(workspace, profile):
    atomic_json(state_path(workspace, profile), {'schema': 1, **binding(for_profile(profile)), 'profile': profile['id'], 'phase': 'unmanaged'})
    return {'note': 'Display management disabled. Current game resolution and Wine Retina setting were preserved; use the game settings to change them.'}


def test_window(workspace, profile, *, control=None, presentation='popup'):
    from .display_test import cancellation
    with cancellation(control) as stopped:
        state = validate_launch(workspace, profile, live=False)
        if not state:
            raise ManagerError('Prepare a display before running the test window.')
        folder = private_dir(Path(workspace) / 'DeadlockData/display-tests' / identifier(profile['id']))
        from datetime import datetime, timezone
        log = folder / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.log')
        with log.open('x') as stream:
            log.chmod(0o600)
            def capture(line):
                stream.write(line)
                stream.flush()
            print(f'The grid stays open until Escape, Close, or Stop Grid. No gameplay starts. Log: {log}', flush=True)
            capture(f'presentation={presentation}\n')
            try:
                output = probe(profile, window_index=state['guest']['index'], stopped=stopped,
                               capture=capture, presentation=presentation)
                if topology(host_inventory()) != state['topology']:
                    raise ManagerError('Display arrangement changed during the test. Prepare it again.')
            except Exception as exc:
                capture(f'diagnostic_error={exc}\n')
                raise ManagerError(f'{exc}\nPartial diagnostic saved: {log}') from exc
    return {'log': str(log), 'output': output,
            'observations': window_observations(output, state['guest']['bounds'][2:]),
            'visual_verification': 'Requires actual coverage, HUD size and Command–Tab confirmation; API coordinates alone are insufficient.'}


def window_observations(output, size):
    width, height = size
    clicks = [tuple(map(int, xy)) for xy in re.findall(r'^pointer_click=(-?\d+),(-?\d+)$', output, re.M)]
    targets = [(80, 80), (width - 80, 80), (80, height - 80), (width - 80, height - 80)]
    hit = [any(abs(x - tx) < 24 and abs(y - ty) < 24 for x, y in clicks) for tx, ty in targets]
    focus = re.findall(r'^window_active=([01])$', output, re.M)
    return {'corner_targets_hit': hit, 'all_corner_targets_hit': all(hit),
            'focus_left_and_returned': '101' in ''.join(focus),
            'closed_normally': 'test_window_closed=yes result=0' in output,
            'close_reason': (re.findall(r'test_window_closed=yes result=\d+ reason=([a-z_]+)', output) or ['unknown'])[0]}
