"""Detached Play lifecycle. Steam launches the game; this process owns Game Mode."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from . import game_mode
from .runtime import clean_env, start
from .storage import ManagerError, atomic_json, lock, no_symlinks


def state_directory():
    # A system-wide policy needs one owner across this user's workspaces/apps.
    return Path.home() / "Library/Application Support/Deadlock Manager/GameMode"


def read_state(directory=None):
    receipt = no_symlinks((directory or state_directory()) / "session.json")
    if not receipt.exists():
        return {"phase": "idle", "restore_pending": False}
    state = json.loads(receipt.read_text())
    if (not isinstance(state, dict) or state.get("schema") != 2
            or state.get("original_policy") not in ("auto", "on", "off")):
        raise ManagerError("Invalid Play recovery receipt; inspect it before changing Game Mode.")
    return state


def status():
    state = read_state()
    pid = state.get("watcher_pid")
    active = bool(state.get("restore_pending") and pid
                  and game_mode.process_identity(pid) == state.get("watcher_identity"))
    return {**state, "watcher_running": active,
            "recovery_needed": bool(state.get("restore_pending") and not active)}


def trial_receipts(workspace):
    return (state_directory() / "game-mode-test.json", workspace / "DeadlockData/game-mode-test.json")


def pending_trial(workspace):
    for receipt in trial_receipts(workspace):
        if receipt.exists() and json.loads(no_symlinks(receipt).read_text()).get("restore_pending"):
            return receipt
    return None


def process_candidates(executable):
    result = subprocess.run(["/bin/ps", "-ww", "-axo", "pid=,comm="],
                            capture_output=True, text=True, timeout=5, env=clean_env())
    if result.returncode:
        raise ManagerError("Could not inspect running Windows processes.")
    return [int(parts[0]) for line in result.stdout.splitlines()
            if len(parts := line.strip().split(None, 1)) == 2 and parts[0].isdigit()
            and parts[1].replace("\\", "/").lower().endswith("/" + executable.lower())]


def game_candidates():
    return process_candidates("deadlock.exe")


def games_in_prefix(prefix):
    return processes_in_prefix(prefix, "deadlock.exe", game_candidates())


def processes_in_prefix(prefix, executable, candidates=None):
    """Read only cwd, not process environments/Steam credentials, to match a bottle."""
    prefix = Path(prefix).resolve()
    games = {}
    for pid in process_candidates(executable) if candidates is None else candidates:
        before = game_mode.process_identity(pid)
        if not before:
            continue
        result = subprocess.run(["/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                                capture_output=True, text=True, timeout=5, env=clean_env())
        if result.returncode:
            if game_mode.process_identity(pid):
                raise ManagerError(f"Could not identify {executable}'s bottle from its working directory.")
            continue  # Process exited during inspection.
        paths = [Path(line[1:]).resolve() for line in result.stdout.splitlines() if line.startswith("n/")]
        if any(path.is_relative_to(prefix) for path in paths):
            identity = game_mode.process_identity(pid)
            if identity == before and identity.replace("\\", "/").lower().endswith("/" + executable.lower()):
                games[pid] = identity
    return games


def restore_policy(tool, receipt, state):
    """Play owns the override until exit, then restores the exact prior policy."""
    if not state.get("restore_pending"):
        return tool.status()
    desired = state["original_policy"]
    if tool.status()["policy"] != desired:
        tool.set(desired)
    final = tool.status()
    if final["policy"] != desired:
        raise ManagerError("Game Mode restoration could not be verified; recovery is still pending.")
    state.update(restore_pending=False, phase="finished", final_status=final,
                 restored_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(receipt, state)
    return final


def recover(directory=None):
    directory = directory or state_directory()
    with lock(directory):
        state = read_state(directory)
        if not state.get("restore_pending"):
            return state
        if games_in_prefix(state["prefix"]):
            raise ManagerError("Deadlock is still running. Use Play for this profile to resume its watcher, or exit the game before recovery.")
        restore_policy(game_mode.AppleTool(state["tool"]), directory / "session.json", state)
        return state


def stop_session(directory=None):
    """Explicit user cancellation, including a game held open by Wine's debugger."""
    directory = directory or state_directory()
    state = read_state(directory)
    if not state.get("restore_pending"):
        return state
    pid = state.get("watcher_pid")
    if not pid or game_mode.process_identity(pid) != state.get("watcher_identity"):
        return recover(directory)
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        state = read_state(directory)
        if not state.get("restore_pending"):
            return state
        if state.get("phase") == "restore-failed":
            raise ManagerError("Restoration failed; use Recover interrupted Play after the game exits.")
        time.sleep(0.2)
    raise ManagerError("The watcher has not confirmed restoration. Check Play session status; recovery is still pending.")


def session(tool, profile, workspace, receipt, launch, ready, startup_seconds=180, previous=None):
    """A startup deadline only; once a game exists its lifetime is unbounded."""
    stopped = False
    handlers = {}

    def stop(*_):
        nonlocal stopped
        stopped = True

    # Adopt an interrupted session without capturing our own 'on' as the original.
    state = previous or {"schema": 2, "original_policy": tool.status()["policy"],
                         "restore_pending": True, "tool": str(tool.path),
                         "workspace": str(workspace), "profile": profile["id"],
                         "prefix": profile["prefix"], "phase": "waiting",
                         "started_utc": datetime.now(timezone.utc).isoformat()}
    state.update(watcher_pid=os.getpid(), watcher_identity=game_mode.process_identity(os.getpid()))
    atomic_json(receipt, state)  # Persist recovery before any policy mutation.
    try:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            handlers[sig] = signal.signal(sig, stop)
        tool.set("on")
        if tool.status() != {"enabled": True, "policy": "on"}:
            raise ManagerError("Apple's tool did not confirm Game Mode on.")
        existing = games_in_prefix(profile["prefix"])
        if not existing and not previous:
            launch()
        ready()
        deadline = time.monotonic() + startup_seconds
        games = {}
        while not stopped:
            games = existing or games_in_prefix(profile["prefix"])
            if games:
                # Track every matching instance, never another bottle or a reused PID.
                state.update(phase="playing", games={str(pid): identity for pid, identity in games.items()})
                atomic_json(receipt, state)
                break
            if time.monotonic() >= deadline:
                raise ManagerError("Deadlock did not start within three minutes. Finish Steam's login/update prompts, then press Play again.")
            time.sleep(1)
        check_policy_at = 0
        while not stopped and games:
            games = {pid: identity for pid, identity in games.items()
                     if game_mode.process_identity(pid) == identity}
            if not games:
                break
            if time.monotonic() >= check_policy_at:
                if tool.status() != {"enabled": True, "policy": "on"}:
                    tool.set("on")
                    if tool.status() != {"enabled": True, "policy": "on"}:
                        raise ManagerError("Game Mode could not be kept on; restoring the prior policy.")
                check_policy_at = time.monotonic() + 10
            time.sleep(1)
    except BaseException as exc:
        state["error"] = str(exc)
        raise
    finally:
        try:
            restore_policy(tool, receipt, state)
        except BaseException as exc:
            state.update(phase="restore-failed", restore_error=str(exc))
            atomic_json(receipt, state)
            raise
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)


def worker(workspace, profile_id, tool_path, response, log):
    # Import here so the detached entry point uses the same profile validation.
    from .cli import load_profile
    from .performance import load
    try:
        with lock(state_directory()):
            profile = load_profile(workspace, profile_id)
            receipt = state_directory() / "session.json"
            previous = read_state()
            if previous.get("restore_pending"):
                old_tool = game_mode.AppleTool(previous["tool"])
                if games_in_prefix(previous["prefix"]):
                    if previous["workspace"] != str(workspace) or previous["profile"] != profile_id:
                        raise ManagerError("An interrupted Game Mode session belongs to another running profile. Resume that profile first.")
                    tool = old_tool
                else:
                    restore_policy(old_tool, receipt, previous)
                    previous = None
            else:
                previous = None
            if previous is None:
                tool = game_mode.AppleTool(tool_path)
            if pending_trial(workspace):
                raise ManagerError("Restore the interrupted diagnostic test with game-mode --restore before Play.")

            def launch():
                start(profile, "launch", log, load(workspace, profile_id))

            def ready():
                atomic_json(response, {"ok": True, "watcher_pid": os.getpid()})
                print("Game Mode enabled. Watching Deadlock until it exits; no play-time limit.", flush=True)

            session(tool, profile, workspace, receipt, launch, ready, previous=previous)
            print("Deadlock session ended; previous Game Mode policy restored.", flush=True)
    except (ManagerError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        if str(exc) == "Another manager operation is running in this workspace.":
            exc = ManagerError("Another Game Mode session is already active. Check Play session status; its policy and game were left unchanged.")
        if not response.exists():
            atomic_json(response, {"ok": False, "error": str(exc)})
        print(f"Game Mode session: {exc}", flush=True)
        return 1
    return 0


def launch_session(workspace, profile_id, tool_path, log):
    """Detach from both CLI and GUI; only a short startup handshake blocks Play."""
    response = log.with_suffix(".session.json")
    watcher_log = log.with_suffix(".watcher.log")
    entry = Path(__file__).with_name("session_worker.py")
    command = [sys.executable, "-I", "-B", str(entry), str(workspace), profile_id,
               str(tool_path) if tool_path else "", str(response), str(log)]
    fd = os.open(watcher_log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                                   stderr=subprocess.STDOUT, env=clean_env(), start_new_session=True)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if response.exists():
            result = json.loads(response.read_text())
            if not result["ok"]:
                raise ManagerError(result["error"])
            return result
        if process.poll() is not None:
            raise ManagerError(f"Game Mode watcher stopped before launch. Inspect {watcher_log}")
        time.sleep(0.1)
    # Never abandon a worker whose startup outcome is unknown without telling it to restore.
    process.terminate()
    raise ManagerError(f"Game Mode startup timed out; the watcher was asked to restore. Check game-mode --session and {watcher_log}")
