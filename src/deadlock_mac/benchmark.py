"""Mark real gameplay windows and summarize existing per-process Metal HUD logs.

No injection, game automation, credentials, player names, or network interception.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import uuid

from . import game_mode, game_session, game_settings, hotfix, performance
from .diagnostics import display_status, power_status
from .runtime import clean_env, steam_path
from .steam import game_status
from .storage import ManagerError, atomic_json, identifier, no_symlinks
from .telemetry import summarize


def now():
    return datetime.now().isoformat(timespec="microseconds")


def folder(workspace):
    return Path(workspace) / "DeadlockData/benchmarks"


def game_log(workspace, pid):
    result = subprocess.run(["/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "1,2", "-Fn"],
                            capture_output=True, text=True, timeout=15, env=clean_env())
    # Steam can redirect stdout to /dev/null while Metal's NSLog uses stderr.
    paths = {Path(line[1:]) for line in result.stdout.splitlines() if line.startswith("n")
             and Path(line[1:]).is_relative_to(Path(workspace) / "DeadlockData/logs")}
    if result.returncode or len(paths) != 1:
        raise ManagerError("Cannot uniquely locate the game's output log. Restart Windows Steam through this manager with HUD logging enabled.")
    path = no_symlinks(next(iter(paths)))
    if not path.is_file() or not path.is_relative_to(Path(workspace) / "DeadlockData/logs"):
        raise ManagerError("Game output is not a private manager log. Restart Windows Steam through this manager.")
    return path


def snapshot():
    state = game_session.status()
    actual = {"verified": False}
    if state.get("tool"):
        try:
            actual = {"verified": True, **game_mode.AppleTool(state["tool"]).status()}
        except (ManagerError, OSError, subprocess.SubprocessError):
            actual = {"verified": False, "error": "Could not query the recorded Apple Game Mode tool."}
    return {"local_time": now(), "power": power_status(),
            "desktop_displays": display_status(),
            "game_mode_actual": actual,
            "game_mode_session": {key: state.get(key) for key in
                                  ("phase", "restore_pending", "watcher_running", "last_status", "final_status")}}


def start(workspace, profile, scenario, resolution):
    if not scenario.strip() or len(scenario) > 100 or len(resolution) > 80:
        raise ManagerError("Use a short scenario and display description; omit personal/player information.")
    if not performance.load(workspace, profile["id"])["hud_logging"]:
        raise ManagerError("Enable performance --hud-log on and restart Steam before recording.")
    games = game_session.games_in_prefix(profile["prefix"])
    if len(games) != 1:
        raise ManagerError("Start exactly one Deadlock game in this profile before recording.")
    pid, identity = next(iter(games.items()))
    path = game_log(workspace, pid)
    info = path.stat()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-").lower() + uuid.uuid4().hex[:8]
    state = {"schema": 1, "id": run_id, "profile": profile["id"], "phase": "recording",
             "start_time": now(), "pid": pid, "process_identity": identity,
             "log": str(path), "log_inode": info.st_ino, "log_device": info.st_dev,
             "start_offset": info.st_size, "scenario": scenario,
             "resolution_user_reported": resolution, "markers": [],
             "runtime_version": profile.get("runtime_version"), "dxmt_version": profile.get("dxmt_version"),
             "wine_hotfix": hotfix.status(profile), "macos": platform.mac_ver()[0],
             "architecture": platform.machine(), "game": game_status(steam_path(profile)),
             "performance_requested": performance.load(workspace, profile["id"]),
             "graphics_before": game_settings.rendering_snapshot(profile),
             "before": snapshot()}
    atomic_json(folder(workspace) / (run_id + ".json"), state)
    return {"id": run_id, "pid": pid, "phase": "recording", "start_time": state["start_time"],
            "note": "HUD logging continues in Steam's existing log. Mark menus/loading and gameplay separately; finish after the match."}


def load(workspace, profile, run_id):
    path = no_symlinks(folder(workspace) / (identifier(run_id) + ".json"))
    state = json.loads(path.read_text())
    if state.get("profile") != profile["id"] or state.get("phase") != "recording":
        raise ManagerError("Benchmark is not recording for this profile.")
    return path, state


def mark(workspace, profile, run_id, label):
    if not label.strip() or len(label) > 100:
        raise ManagerError("Use a short marker label without player information.")
    path, state = load(workspace, profile, run_id)
    event = {"local_time": now(), "label": label}
    state["markers"].append(event)
    atomic_json(path, state)
    return event


def finish(workspace, profile, run_id, warmup_seconds=0):
    path, state = load(workspace, profile, run_id)
    log = no_symlinks(state["log"])
    if not log.is_relative_to(Path(workspace) / "DeadlockData/logs"):
        raise ManagerError("Benchmark log escaped private manager storage.")
    end = now()
    fd = os.open(log, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (info.st_dev, info.st_ino) != (state["log_device"], state["log_inode"]) or info.st_size < state["start_offset"]:
            raise ManagerError("HUD log was replaced or truncated; this benchmark cannot be compared reliably.")
        stream.seek(state["start_offset"])
        lines = (line.decode("utf-8", errors="replace") for line in stream)
        metrics = summarize(lines, state["pid"], warmup_seconds, state["start_time"], end)
    report = {key: state[key] for key in ("schema", "id", "profile", "pid", "start_time", "scenario",
                                        "resolution_user_reported", "markers", "runtime_version", "dxmt_version",
                                        "wine_hotfix", "macos", "architecture", "game", "performance_requested", "before")}
    graphics_before = state.get("graphics_before", {"available": False})
    graphics_after = game_settings.rendering_snapshot(profile)
    unchanged = (graphics_before["sha256"] == graphics_after["sha256"]
                 and graphics_before.get("fps_limits") == graphics_after.get("fps_limits")
                 if graphics_before.get("available") and graphics_after.get("available") else None)
    report.update(end_time=end, after=snapshot(), metrics=metrics,
                  graphics_before=graphics_before, graphics_after=graphics_after,
                  saved_graphics_unchanged=unchanged,
                  limitations="User-marked observation, not a deterministic benchmark. Power and Game Mode receipt sampled only at boundaries; not continuous thermal/GPU-utilization telemetry. Report includes loading/focus gaps unless excluded explicitly. Review free-text labels before sharing.")
    atomic_json(folder(workspace) / (run_id + "-report.json"), report)
    state.update(phase="finished", end_time=end)
    atomic_json(path, state)
    return report
