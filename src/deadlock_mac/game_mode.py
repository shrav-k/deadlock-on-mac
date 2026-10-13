"""Optional Apple developer-tool diagnostics, independent of the Wine adapter.

Game Mode's policy is system-wide. A bounded test is never a launch default and
does not establish that an anonymous Wine process receives per-game priority.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import time

from .runtime import clean_env
from .storage import ManagerError, atomic_json, no_symlinks


def parse_status(output):
    text = re.sub(r"\x1b\[[0-9;]*m", "", output)
    mode = re.search(r"^Game mode is (on|off)\.", text, re.MULTILINE)
    policies = []
    for policy, phrase in (("auto", "policy is currently automatic."),
                           ("on", "Game mode is forced always on."),
                           ("off", "Game mode is forced always off.")):
        if phrase in text:
            policies.append(policy)
    if not mode or len(policies) != 1:
        raise ManagerError("Unrecognized gamepolicyctl status; no policy change is safe.")
    return {"enabled": mode[1] == "on", "policy": policies[0]}


class AppleTool:
    def __init__(self, path=None):
        if platform.system() != "Darwin":
            raise ManagerError("Apple Game Mode diagnostics require macOS.")
        if path is None:
            result = subprocess.run(["/usr/bin/xcrun", "--find", "gamepolicyctl"],
                                    capture_output=True, text=True, timeout=10, env=clean_env())
            if result.returncode:
                raise ManagerError("No gamepolicyctl found in the selected Xcode. Normal game launch is still available.")
            path = result.stdout.strip()
        self.path = Path(path).expanduser().resolve(strict=True)
        if not self.path.is_file() or not os.access(self.path, os.X_OK):
            raise ManagerError("gamepolicyctl must be an executable file.")
        verified = subprocess.run(["/usr/bin/codesign", "--verify", "--strict", "-R",
                                   '=anchor apple and identifier "com.apple.gamepolicyctl"', str(self.path)],
                                  capture_output=True, text=True, timeout=15, env=clean_env())
        if verified.returncode:
            raise ManagerError("The tool failed Apple's signature/identity requirement; it was not executed.")

    def run(self, *arguments):
        result = subprocess.run([str(self.path), "game-mode", *arguments], capture_output=True,
                                text=True, timeout=10, env=clean_env())
        if result.returncode:
            raise ManagerError("Apple's Game Mode tool failed. Its version may be incompatible with this macOS; use a compatible Xcode tool.")
        return result.stdout

    def status(self):
        return parse_status(self.run("status"))

    def set(self, policy):
        if policy not in ("auto", "on", "off"):
            raise ManagerError("Invalid Game Mode policy.")
        self.run("set", policy)


def process_identity(pid):
    if type(pid) is not int or pid <= 0:
        raise ManagerError("A positive native Deadlock process ID is required.")
    result = subprocess.run(["/bin/ps", "-ww", "-p", str(pid), "-o", "lstart=,comm="],
                            capture_output=True, text=True, timeout=5, env=clean_env())
    return result.stdout.strip() if result.returncode == 0 else ""


def restore(tool, receipt):
    """Restore a recorded test, preserving a later explicit off/auto policy."""
    receipt = no_symlinks(receipt)
    state = json.loads(receipt.read_text())
    if not isinstance(state, dict) or state.get("schema") != 1 or state.get("original_policy") != "auto":
        raise ManagerError("Invalid Game Mode recovery receipt.")
    if not state.get("restore_pending"):
        return tool.status()
    current = tool.status()
    if current["policy"] == "on":
        tool.set("auto")
        current = tool.status()
        if current["policy"] != "auto":
            raise ManagerError("Could not verify Game Mode restoration; recovery receipt retained.")
    state.update(restore_pending=False, final_status=current,
                 restored_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(receipt, state)
    return current


def trial(tool, pid, seconds, receipt, report=print):
    if type(seconds) is not int or not 1 <= seconds <= 900:
        raise ManagerError("Game Mode tests must last between 1 and 900 seconds.")
    receipt = no_symlinks(receipt)
    identity = process_identity(pid)
    if not identity.lower().endswith("\\deadlock.exe"):
        raise ManagerError("The selected PID is not a running Windows Deadlock process.")
    if receipt.exists():
        previous = json.loads(receipt.read_text())
        if not isinstance(previous, dict) or previous.get("schema") != 1:
            raise ManagerError("Invalid Game Mode recovery receipt; inspect it before testing.")
        if previous.get("restore_pending"):
            raise ManagerError("A previous Game Mode test needs --restore before another can start.")
    before = tool.status()
    if before["policy"] != "auto":
        raise ManagerError("A Game Mode override already exists. This test requires automatic policy.")
    state = {"schema": 1, "original_policy": "auto", "restore_pending": True,
             "tool": str(tool.path), "pid": pid, "process_identity": identity,
             "maximum_seconds": seconds, "started_utc": datetime.now(timezone.utc).isoformat()}
    atomic_json(receipt, state)  # Recovery must exist before the first mutation.
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True

    handlers = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            handlers[sig] = signal.signal(sig, stop)
        tool.set("on")
        enabled = tool.status()
        if enabled != {"enabled": True, "policy": "on"}:
            raise ManagerError("Apple's tool did not confirm Game Mode on.")
        report(f"Game Mode is on for a test of at most {seconds} seconds. Check Deadlock's HUD. Ctrl-C ends and restores the test.")
        deadline = time.monotonic() + seconds
        while not stopped and time.monotonic() < deadline and process_identity(pid) == identity:
            time.sleep(min(1, max(0, deadline - time.monotonic())))
    finally:
        try:
            final = restore(tool, receipt)
            report(f"Game Mode test finished; current policy: {final['policy']}.")
        finally:
            for sig, previous in handlers.items():
                signal.signal(sig, previous)
    return final
