"""Reversible launch settings; never edits game saves or global macOS settings."""
import json
from pathlib import Path

from .storage import ManagerError, atomic_json, identifier

DEFAULTS = {"schema": 1, "fps_cap": 0, "sync": "auto", "metal_hud": False,
            "hud_logging": False}


def validate(settings):
    if not isinstance(settings, dict) or set(settings) != set(DEFAULTS):
        raise ManagerError("Invalid performance settings schema.")
    if settings["schema"] != 1 or type(settings["fps_cap"]) is not int or not 0 <= settings["fps_cap"] <= 360:
        raise ManagerError("FPS cap must be an integer from 0 (uncapped) to 360.")
    if settings["sync"] not in ("auto", "none", "msync", "esync"):
        raise ManagerError("Unknown synchronization mode.")
    if any(type(settings[k]) is not bool for k in ("metal_hud", "hud_logging")):
        raise ManagerError("HUD settings must be booleans.")
    if settings["hud_logging"] and not settings["metal_hud"]:
        raise ManagerError("HUD logging requires the Metal HUD to be enabled.")
    return settings


def settings_path(workspace, profile_id):
    return Path(workspace) / "DeadlockData/performance" / (identifier(profile_id) + ".json")


def load(workspace, profile_id):
    path = settings_path(workspace, profile_id)
    if path.is_symlink():
        raise ManagerError("Refusing linked performance settings.")
    return validate(json.loads(path.read_text())) if path.exists() else dict(DEFAULTS)


def save(workspace, profile, settings, *, check_running=None):
    # Sync is fixed when wineserver starts and Steam passes its environment to
    # games. A second launcher cannot change an already-running client's env.
    from .backup import wine_processes_running
    if profile["provider"] != "wine":
        raise ManagerError("Configure the official CrossOver provider in CrossOver itself.")
    if (check_running or wine_processes_running)():
        raise ManagerError("Exit Windows Steam and all Wine bottles before changing performance settings.")
    atomic_json(settings_path(workspace, profile["id"]), validate(settings))


def variables(settings):
    settings = validate(settings)
    env = {}
    if settings["fps_cap"]:
        env["DXMT_CONFIG"] = f"d3d11.preferredMaxFrameRate={settings['fps_cap']};"
    if settings["sync"] != "auto":
        env["WINEMSYNC"] = "1" if settings["sync"] == "msync" else "0"
        env["WINEESYNC"] = "1" if settings["sync"] == "esync" else "0"
    if settings["metal_hud"]:
        env["MTL_HUD_ENABLED"] = "1"
    if settings["hud_logging"]:
        env["MTL_HUD_LOG_ENABLED"] = "1"
    return env
