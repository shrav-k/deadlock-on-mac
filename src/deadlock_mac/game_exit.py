"""Request normal game shutdown, then verify actual exit and policy restoration."""
import os
import subprocess
import time

from . import game_mode, game_session
from .runtime import environment, exit_command, verify_crossover
from .storage import ManagerError


def finish_session(workspace, profile_id, timeout=20):
    deadline = time.monotonic() + timeout
    while True:
        state = game_session.status()
        if state.get("workspace") != str(workspace) or state.get("profile") != profile_id:
            return "No Game Mode session belongs to this profile."
        if not state.get("restore_pending"):
            return f"Game Mode restored to {state.get('final_status', {}).get('policy', state.get('original_policy', 'unknown'))}."
        if time.monotonic() >= deadline:
            raise ManagerError("Deadlock exited, but Game Mode restoration is still pending. Check Play session status.")
        if state.get("recovery_needed"):
            game_session.recover()
        time.sleep(0.5)


def close(workspace, profile, log, timeout=30, report=print):
    games = game_session.games_in_prefix(profile["prefix"])
    if len(games) > 1:
        raise ManagerError("Multiple Deadlock processes are running in this bottle; close them in the game before retrying.")
    if not games:
        return "Deadlock is already closed. " + finish_session(workspace, profile["id"])
    pid, identity = next(iter(games.items()))
    if profile["provider"] == "crossover":
        verify_crossover(profile["runtime"])
    command = exit_command(profile)
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        result = subprocess.run(command, env=environment(profile), cwd=profile["prefix"],
                                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, timeout=15)
    if result.returncode and game_mode.process_identity(pid) == identity:
        raise ManagerError(f"Could not request a normal Deadlock close. See {log}. No process was force-killed.")
    report("Normal close requested. Waiting for Deadlock to exit; Steam stays open.")
    deadline = time.monotonic() + timeout
    while game_mode.process_identity(pid) == identity:
        if time.monotonic() >= deadline:
            raise ManagerError("Deadlock has not exited. Check for an in-game confirmation or Wine error dialog; the manager did not force-kill it.")
        time.sleep(0.5)
    return "Deadlock exited. Steam remains open for synchronization. " + finish_session(workspace, profile["id"])
