"""Apple tool verification and timed diagnostics; Play lifetime is in game_session.

The system-wide policy does not establish native per-game eligibility under Wine.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import signal
import shutil
import subprocess
import tempfile
import time

from .runtime import clean_env
from .storage import ManagerError, atomic_json, no_symlinks, private_dir, sha256

SETUP_HELP = ("Game Mode needs a compatible Apple-signed gamepolicyctl. Install or update Xcode "
              "from Apple, then use Check Game Mode Setup again; no file selection or xcode-select "
              "change is needed. Alternatively explicitly turn off Enable during Play.")


def tool_candidates(workspace=None):
    """Known Apple locations only; never execute tools found on an inherited PATH."""
    candidates = []
    if workspace is not None:
        directory = no_symlinks(Path(workspace) / 'DeadlockData/tools/game-mode')
        receipt = directory / 'current.json'
        if receipt.is_file():
            try:
                digest = json.loads(no_symlinks(receipt).read_text()).get('sha256', '')
                if isinstance(digest, str) and re.fullmatch(r'[a-f0-9]{64}', digest):
                    cached = no_symlinks(directory / digest / 'gamepolicyctl')
                    if cached.is_file() and sha256(cached) == digest:
                        candidates.append(cached)
            except (OSError, ValueError, AttributeError):
                pass  # Discovery still verifies every other candidate independently.
        # Migrate the old local diagnostic installation without a file-picker step.
        candidates.append(Path(workspace) / 'Tools/game-mode-investigation/gamepolicyctl')
    try:
        result = subprocess.run(['/usr/bin/xcrun', '--find', 'gamepolicyctl'],
                                capture_output=True, text=True, timeout=10, env=clean_env())
        if result.returncode == 0 and Path(result.stdout.strip()).is_absolute():
            candidates.append(Path(result.stdout.strip()))
    except (OSError, subprocess.SubprocessError):
        pass
    for directory in (Path('/Applications'), Path.home() / 'Applications'):
        candidates.extend(sorted(directory.glob('Xcode*.app/Contents/Developer/usr/bin/gamepolicyctl')))
    seen = set()
    for path in candidates:
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            continue
        if resolved not in seen:
            seen.add(resolved)
            yield resolved


def select_tool(workspace=None):
    failures = []
    for path in tool_candidates(workspace):
        try:
            tool = AppleTool(path)
            tool.status()  # A valid Apple signature alone does not imply OS compatibility.
            return tool
        except (ManagerError, OSError, subprocess.SubprocessError) as exc:
            failures.append(f'{path.name}: {exc}')
    detail = ' No compatible tool passed signature and status checks.' if failures else ''
    raise ManagerError(SETUP_HELP + detail)


def prepare_tool(workspace, path=None):
    """Keep a verified local copy so an Xcode move/update does not break recovery."""
    tool = AppleTool(path) if path is not None else select_tool(workspace)
    before = tool.status()
    digest = sha256(tool.path)
    parent = private_dir(Path(workspace) / 'DeadlockData/tools/game-mode')
    destination = no_symlinks(parent / digest)
    if not destination.exists():
        with tempfile.TemporaryDirectory(prefix='.prepare-', dir=parent) as temporary:
            staged = Path(temporary) / 'payload'; staged.mkdir(mode=0o700)
            candidate = staged / 'gamepolicyctl'
            shutil.copyfile(tool.path, candidate); candidate.chmod(0o700)
            if sha256(candidate) != digest:
                raise ManagerError('Apple tool changed while preparing it; retry setup.')
            AppleTool(candidate).status()
            try:
                staged.rename(destination)
            except FileExistsError:
                pass  # Another preparer may have published the identical digest.
    cached = no_symlinks(destination / 'gamepolicyctl')
    if not cached.is_file() or sha256(cached) != digest:
        raise ManagerError('Prepared Apple tool failed integrity validation; preserve it for inspection.')
    current = AppleTool(cached).status()
    if current['policy'] != before['policy']:
        raise ManagerError('Game Mode policy changed during setup; no policy was set by this operation.')
    record = {'schema': 1, 'sha256': digest, 'source': str(tool.path),
              'macos': platform.mac_ver()[0], 'path': str(cached), 'status': current}
    atomic_json(parent / 'current.json', record)
    return {'ready': True, 'backend': 'apple-tool', **record}


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
    def __init__(self, path=None, workspace=None):
        if platform.system() != "Darwin":
            raise ManagerError("Apple Game Mode diagnostics require macOS.")
        if path is None:
            path = select_tool(workspace).path
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


def find_game():
    result = subprocess.run(["/bin/ps", "-ww", "-axo", "pid=,comm="],
                            capture_output=True, text=True, timeout=5, env=clean_env())
    if result.returncode:
        raise ManagerError("Could not inspect running game processes.")
    return select_game(result.stdout)


def select_game(processes):
    candidates = []
    for line in processes.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].lower().endswith("\\deadlock.exe"):
            candidates.append(int(parts[0]))
    if len(candidates) != 1:
        raise ManagerError("Expected exactly one running Deadlock game. Launch it through Steam first; use --test-pid when comparing multiple instances.")
    return candidates[0]


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


def trial(tool, pid, seconds, receipt, report=print, cancelled=None):
    if cancelled is not None and cancelled.is_set():
        raise ManagerError("Game Mode diagnostic cancelled before startup.")
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
        while not stopped and not (cancelled is not None and cancelled.is_set()) and time.monotonic() < deadline and process_identity(pid) == identity:
            time.sleep(min(1, max(0, deadline - time.monotonic())))
    finally:
        try:
            final = restore(tool, receipt)
            report(f"Game Mode test finished; current policy: {final['policy']}.")
        finally:
            for sig, previous in handlers.items():
                signal.signal(sig, previous)
    return final
