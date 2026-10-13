"""Narrow, backed-up graphics edits for the tested Deadlock video schema."""
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile

from .runtime import steam_path
from .steam import parse_vdf
from .storage import ManagerError, atomic_json, no_symlinks, private_dir, sha256

BALANCED_1080 = {"setting.defaultres": "1920", "setting.defaultresheight": "1080",
                 "setting.fullscreen": "1", "setting.coop_fullscreen": "0",
                 "setting.nowindowborder": "0"}


def video_file(profile):
    base = steam_path(profile).parent
    matches = list((base / "userdata").glob("*/1422450/local/cfg/video.txt"))
    if len(matches) != 1:
        raise ManagerError("Expected exactly one Deadlock video configuration. Start the game once, or configure graphics in game when multiple accounts exist.")
    return no_symlinks(matches[0])


def plan(profile):
    path = video_file(profile)
    if path.stat().st_size > 256 * 1024:
        raise ManagerError("Unexpectedly large video configuration.")
    content = path.read_text()
    value = parse_vdf(content)
    video = value.get("video.cfg")
    if not isinstance(video, dict) or video.get("Version") != "20" or any(not isinstance(v, str) for v in video.values()):
        raise ManagerError("Untested video configuration schema; use Deadlock's graphics menu.")
    if not set(BALANCED_1080).issubset(video):
        raise ManagerError("Expected resolution settings are missing; use the game's graphics menu.")
    return path, content, video


def configure(workspace, profile, *, apply=False, check_running=None):
    from .backup import wine_processes_running
    if apply and (check_running or wine_processes_running)():
        raise ManagerError("Exit Windows Steam and all Wine bottles before editing graphics settings.")
    path, original, video = plan(profile)
    changes = {key: {"before": video[key], "after": value} for key, value in BALANCED_1080.items()}
    if not apply:
        return {"applied": False, "changes": changes, "note": "Only output resolution/display mode change; existing render scale and quality are preserved."}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = private_dir(Path(workspace) / "DeadlockData/settings-backups" / profile["id"] / stamp)
    with (backup / "video.txt").open("x") as stream:
        stream.write(original)
    (backup / "video.txt").chmod(0o600)
    atomic_json(backup / "receipt.json", {"schema": 1, "file": str(path.relative_to(Path(profile["prefix"]))),
                                         "before_sha256": sha256(path), "changes": changes})
    # Replace only the selected values, preserving every other byte and key.
    import re
    modified = original
    for key, value in BALANCED_1080.items():
        modified, count = re.subn(r'("' + re.escape(key) + r'"\s+")[^"]*(")',
                                  lambda m: m.group(1) + value + m.group(2), modified)
        if count != 1:
            raise ManagerError("Ambiguous graphics key; original configuration was preserved.")
    if path.read_text() != original:
        raise ManagerError("Configuration changed during preparation; retry with Steam closed.")
    fd, temporary = tempfile.mkstemp(prefix=".video-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(modified)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"applied": True, "changes": changes, "backup": str(backup),
            "note": "Confirm fullscreen resolution and render scale in the game. Steam Cloud decisions remain manual."}
