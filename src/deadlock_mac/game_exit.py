"""Request normal game shutdown, then verify actual exit and policy restoration."""
import os
from pathlib import Path
import subprocess
import time

from . import game_mode, game_session
from .runtime import environment, exit_command, steam_control_command, verify_crossover
from .storage import ManagerError


def finish_session(workspace, profile_id, timeout=20):
    deadline = time.monotonic() + timeout
    while True:
        state = game_session.status()
        if state.get("workspace") != str(workspace) or state.get("profile") != profile_id:
            return "No Game Mode session belongs to this profile."
        if not state.get("restore_pending"):
            return f"Game Mode restored to {state.get('final_status', {}).get('policy', state.get('original_policy', 'unknown'))}."
        if state.get("watcher_running") and state.get("phase") == "waiting":
            raise ManagerError("Play is still starting. Wait for Deadlock to appear, then retry Exit.")
        if time.monotonic() >= deadline:
            raise ManagerError("Deadlock exited, but Game Mode restoration is still pending. Check Play session status.")
        if state.get("recovery_needed"):
            game_session.recover()
        time.sleep(0.5)


def send(profile, command, log):
    if profile["provider"] == "crossover":
        verify_crossover(profile["runtime"])
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        return subprocess.run(command, env=environment(profile), cwd=profile["prefix"],
                              stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, timeout=15)


def wait_for_exit(processes, timeout):
    deadline = time.monotonic() + timeout
    while any(game_mode.process_identity(pid) == identity for pid, identity in processes.items()):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)
    return True


def wait_for_wine_shutdown(profile, timeout=20):
    """Wait for this prefix's server grace period; never stop another bottle.

    Steam's client can disappear before wineserver finishes. A subsequent display
    probe otherwise mistakes that retiring server for an unrelated live session.
    --wait observes shutdown; it neither starts Steam nor kills the server.
    """
    if profile['provider'] != 'wine':
        return  # CrossOver owns its bottle lifecycle; do not guess its server path.
    try:
        result = subprocess.run([str(Path(profile['runtime']) / 'bin/wineserver'), '--wait'],
                                env=environment(profile), cwd=profile['prefix'],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ManagerError('Windows Steam closed, but Wine is still finishing shutdown. '
                           'Wait or close other apps in this bottle, then retry. No process was force-killed.') from exc
    if result.returncode:
        raise ManagerError('Windows Steam closed, but Wine server shutdown could not be verified. '
                           'Inspect this profile before restarting.')


def close(workspace, profile, log, timeout=30, report=print):
    games = game_session.games_in_prefix(profile["prefix"])
    if len(games) > 1:
        raise ManagerError("Multiple Deadlock processes are running in this bottle; close them in the game before retrying.")
    if not games:
        return "Deadlock is already closed. " + finish_session(workspace, profile["id"])
    pid, identity = next(iter(games.items()))
    if not game_session.processes_in_prefix(profile["prefix"], "steam.exe"):
        raise ManagerError("Windows Steam is not running in this profile. Use Deadlock's Exit Game option.")
    if game_mode.process_identity(pid) != identity:
        raise ManagerError("Deadlock changed while preparing Exit. Retry to inspect the current process.")
    result = send(profile, exit_command(profile), log)
    if result.returncode and game_mode.process_identity(pid) == identity:
        raise ManagerError(f"Could not request a normal Deadlock close. See {log}. No process was force-killed.")
    report("Steam was asked to stop Deadlock normally. Waiting for actual exit; Steam stays open.")
    if not wait_for_exit(games, timeout):
        raise ManagerError("Steam's stop request did not close Deadlock. Check for a confirmation or Wine error dialog and inspect Play session status. No process was force-killed or Game Mode restoration claimed.")
    if game_session.games_in_prefix(profile["prefix"]):
        raise ManagerError("Another Deadlock process appeared during Exit. Retry; Game Mode restoration has not been claimed.")
    return "Deadlock exited. Steam remains open for synchronization. " + finish_session(workspace, profile["id"])


def close_steam(workspace, profile, log, timeout=60, report=print):
    """Close Deadlock first; Steam's own shutdown owns saves/downloads/prompts."""
    report(close(workspace, profile, log.with_suffix(".game.log"), report=report))
    clients = game_session.processes_in_prefix(profile["prefix"], "steam.exe")
    if len(clients) > 1:
        raise ManagerError("Multiple Windows Steam clients belong to this profile; shutdown was not sent.")
    # Recheck the game after restoration, before asking Steam to shut down.
    if game_session.games_in_prefix(profile["prefix"]):
        raise ManagerError("Deadlock started again. Close it before exiting Steam.")
    if clients:
        result = send(profile, steam_control_command(profile, "steam"), log)
        if result.returncode and any(game_mode.process_identity(pid) == identity for pid, identity in clients.items()):
            raise ManagerError(f"Could not request Windows Steam shutdown. See {log}.")
        report(f"Shutdown requested; waiting up to {timeout:g}s for Windows Steam and its helpers. Check Steam for prompts.")
    deadline = time.monotonic() + timeout
    next_report = time.monotonic() + 5
    while any(game_session.processes_in_prefix(profile["prefix"], name)
              for name in ("steam.exe", "steamwebhelper.exe", "steamservice.exe", "gameoverlayui.exe")):
        if time.monotonic() >= deadline:
            raise ManagerError("Windows Steam did not close within the timeout. Check Steam for prompts or use Steam → Exit. You can quit the manager and retry after restarting Steam; no process was force-killed.")
        if time.monotonic() >= next_report:
            report(f"Still waiting for Windows Steam ({max(0, deadline - time.monotonic()):.0f}s left). Check Steam for prompts; Quit Manager will wait for this step.")
            next_report = time.monotonic() + 5
        time.sleep(0.5)
    if profile['provider'] == 'wine':
        report('Steam clients are closed. Waiting for this profile\'s Wine session to finish…')
    wait_for_wine_shutdown(profile)
    message = "Windows Steam and its helpers exited. " if clients else "Windows Steam and its helpers are closed. "
    return message + finish_session(workspace, profile["id"])
