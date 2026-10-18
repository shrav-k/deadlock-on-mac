"""Observed, local-only visual testing for one Wine profile.

ScreenCaptureKit captures the composited Metal window; no game injection. Input
requires an enabled session, a fresh unused capture, unchanged process/geometry,
and native foreground validation. Each action returns a new capture for review.
"""
import json
import math
from pathlib import Path
import plistlib
import subprocess
import time
import uuid

from . import game_session, game_mode
from .games import for_profile, from_receipt, binding, require_deadlock
from .runtime import clean_env
from .storage import ManagerError, atomic_json, identifier, no_symlinks, private_dir, sha256

TARGETS = {"game": (), "deadlock": (), "steam": ("steam.exe", "steamwebhelper.exe"),
           "grid": ("wine-displays.exe",)}
KEYS = {"escape", "return", "tab", "space", "left", "right", "up", "down",
        "w", "a", "s", "d", "q", "e", "1", "2", "3", "4"}
MAX_AGE = 60
MAX_STORAGE = 512 * 1024**2


def folder(workspace, profile):
    return no_symlinks(Path(workspace) / "DeadlockData/visual" / identifier(profile["id"]))


def native(workspace, request):
    packaged = Path(__file__).resolve().parents[4] / "MacOS/DeadlockManager"
    executable = packaged if packaged.is_file() else Path(workspace) / "Builds/Deadlock Manager.app/Contents/MacOS/DeadlockManager"
    executable = no_symlinks(executable)
    info = executable.parent.parent / "Info.plist"
    if not executable.is_file() or not info.is_file() or plistlib.loads(info.read_bytes()).get("CFBundleIdentifier") != "dev.shrav-k.deadlock-manager":
        raise ManagerError("Build/install the current Deadlock Manager app before using visual testing.")
    try:
        result = subprocess.run([str(executable), "--visual-worker"], input=json.dumps(request),
                                capture_output=True, text=True, env=clean_env(), timeout=25)
    except subprocess.TimeoutExpired as exc:
        raise ManagerError("Visual operation timed out. Handle any macOS permission prompt and retry; no success is assumed.") from exc
    try:
        reply = json.loads(result.stdout)
    except ValueError as exc:
        raise ManagerError("Visual worker returned no valid response. Install the current app and check permissions.") from exc
    if result.returncode or "error" in reply:
        raise ManagerError(reply.get("error", "Visual worker failed."))
    return reply


def candidates(profile, target):
    if profile.get("provider") != "wine" or target not in TARGETS:
        raise ManagerError("Choose game, steam or grid in a Wine profile (deadlock remains a legacy alias).")
    if target == "deadlock":
        require_deadlock(profile, "The deadlock capture alias")
    names = (for_profile(profile).process_name,) if target in ("game", "deadlock") else TARGETS[target]
    result = {}
    for name in names:
        result.update(game_session.processes_in_prefix(profile["prefix"], name))
    if not result:
        raise ManagerError(f"No running {target} process in this profile.")
    return {str(pid): identity for pid, identity in result.items()}


def request(profile, target):
    return {"prefix": str(profile["prefix"]), "profile": profile["id"], "candidates": candidates(profile, target)}


def permissions(workspace, action="status", backend=native):
    if action not in ("status", "request-screen", "request-input"):
        raise ManagerError("Unknown permission action.")
    return backend(workspace, {"command": action})


def session(workspace, profile, enabled=None):
    path = folder(workspace, profile) / "input-session.json"
    if enabled is not None:
        atomic_json(path, {"schema": 1, **binding(for_profile(profile)), "profile": profile["id"], "enabled": bool(enabled),
                           "expires_at": time.time() + 4 * 3600 if enabled else 0})
    value = json.loads(path.read_text()) if path.exists() else {"enabled": False, "expires_at": 0}
    return {**value, "active": value.get("enabled") is True and value.get("expires_at", 0) > time.time()
            and from_receipt(value) == for_profile(profile)}


def windows(workspace, profile, target, backend=native):
    scoped = request(profile, target)
    return backend(workspace, {**scoped, "command": "windows"})


def capture(workspace, profile, target, window_id=None, backend=native):
    scoped = request(profile, target)
    items = backend(workspace, {**scoped, "command": "windows"})["windows"]
    if window_id is not None:
        items = [item for item in items if item["window_id"] == window_id]
    if not items:
        raise ManagerError("No visible window for this target. Open it, then retry.")
    # Prefer a visible window, then largest; another Space is capturable too.
    # Capture a normal application window, never a full desktop. Explicit
    # --window selects smaller dialogs; input still requires a frontmost check.
    items.sort(key=lambda w: (w.get("on_screen", False), w["bounds"][2] * w["bounds"][3]), reverse=True)
    selected = items[0]
    if str(selected["pid"]) not in scoped["candidates"]:
        raise ManagerError("Capture backend returned an unrelated process.")
    root = private_dir(folder(workspace, profile))
    if sum(p.stat().st_size for p in root.glob("*.png") if not p.is_symlink()) >= MAX_STORAGE:
        raise ManagerError("Private captures reached the 512 MiB limit. Review/remove old test captures before continuing.")
    capture_id = uuid.uuid4().hex
    image = root / (capture_id + ".png")
    try:
        identity = scoped["candidates"][str(selected["pid"])]
        reply = backend(workspace, {**scoped, "candidates": {str(selected["pid"]): identity},
                                    "command": "capture", "window_id": selected["window_id"], "output": str(image)})
        if (reply["pid"] != selected["pid"] or reply["window_id"] != selected["window_id"]
                or game_mode.process_identity(selected["pid"]) != identity):
            raise ManagerError("Target changed during capture; no input receipt created.")
        no_symlinks(image)
        if not image.is_file() or image.stat().st_size == 0:
            raise ManagerError("Capture produced no image.")
        image.chmod(0o600)
        state = {**reply, "schema": 1, **binding(for_profile(profile)), "id": capture_id, "profile": profile["id"], "target": target,
                 "prefix": str(profile["prefix"]), "created_at": time.time(), "process_identity": identity,
                 "image_sha256": sha256(image), "input_used": False}
        atomic_json(root / (capture_id + ".json"), state)
        return state
    except BaseException:
        # Only this attempt's own newly allocated image may be removed.
        image.unlink(missing_ok=True)
        raise


def validate_input(state, profile, command, x=None, y=None, key=None, now=None, hold_ms=40):
    now = time.time() if now is None else now
    if (state.get("schema") != 1 or state.get("profile") != profile["id"]
            or from_receipt(state) != for_profile(profile)
            or state.get("prefix") != str(profile["prefix"]) or state.get("target") not in TARGETS
            or state.get("input_used") is not False
            or not 0 <= now - state.get("created_at", 0) <= MAX_AGE):
        raise ManagerError("Capture is stale, already used, or belongs to another profile. Capture and inspect again.")
    if command == "click":
        width, height = state["pixels"]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (x, y)) or not (0 <= x < width and 0 <= y < height):
            raise ManagerError("Click coordinates must be inside the captured PNG.")
    elif command != "key" or key not in KEYS:
        raise ManagerError("Use one supported navigation/game key; arbitrary text and key chords are not accepted.")
    if (type(hold_ms) is not int or not 40 <= hold_ms <= 1000
            or (hold_ms != 40 and (command != "key" or key not in {"w", "a", "s", "d"}))):
        raise ManagerError("Only movement keys can be held, for 40–1000 ms per observed action.")


def act(workspace, profile, capture_id, command, x=None, y=None, key=None, backend=native, hold_ms=40):
    identifier(capture_id)
    root = folder(workspace, profile)
    receipt = no_symlinks(root / (capture_id + ".json"))
    state = json.loads(receipt.read_text())
    if not session(workspace, profile)["active"]:
        raise ManagerError("Enable a visual input session in Diagnostics first. Stop Input revokes it.")
    validate_input(state, profile, command, x, y, key, hold_ms=hold_ms)
    image = no_symlinks(root / (capture_id + ".png"))
    if sha256(image) != state["image_sha256"]:
        raise ManagerError("Capture image changed; take a fresh screenshot.")
    scoped = request(profile, state["target"])
    if scoped["candidates"].get(str(state["pid"])) != state["process_identity"]:
        raise ManagerError("Captured process exited or its PID was reused. No input sent.")
    # Consume before dispatch: a timeout/unknown outcome must never be retried
    # against the same image. A failed action also requires a fresh observation.
    state["input_used"] = True
    atomic_json(receipt, state)
    payload = {**scoped, "command": command, "window_id": state["window_id"], "bounds": state["bounds"],
               "candidates": {str(state["pid"]): state["process_identity"]},
               "pixels": state["pixels"], "x": x, "y": y, "key": key, "hold_ms": hold_ms,
               "grant_path": str(root / "input-session.json")}
    try:
        result = backend(workspace, payload)
        time.sleep(.25)
        after = capture(workspace, profile, state["target"], state["window_id"], backend)
    except Exception as exc:
        atomic_json(root / (capture_id + "-action.json"), {"command": command, "error": str(exc), "effect_verified": False})
        raise
    action = {"command": command, "x": x, "y": y, "key": key, "hold_ms": hold_ms, "result": result,
              "after": after["id"], "effect_verified": False}
    atomic_json(root / (capture_id + "-action.json"), action)
    return {"action": action, "capture": after}
