"""Narrow, backed-up graphics edits for the tested Deadlock video schema."""
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile

from ..runtime import steam_path
from ..steam import parse_vdf
from ..storage import ManagerError, atomic_json, no_symlinks, private_dir, sha256

BACKUP_SCOPE = "Deadlock userdata and game/citadel/cfg; not a full bottle backup"

BALANCED_1080 = {"setting.defaultres": "1920", "setting.defaultresheight": "1080",
                 "setting.fullscreen": "1", "setting.coop_fullscreen": "0",
                 "setting.nowindowborder": "0"}

# Enabling custom settings prevents a named quality preset from reapplying its
# reduced viewport scale. Quality, output size and ordinary AA remain untouched.
NATIVE_RENDERING = {"setting.mat_viewportscale": "1", "setting.useadvanced": "1",
                    "setting.r_citadel_upscaling": "0",
                    "setting.r_citadel_dlss_settings_mode": "0"}


def configure_native(workspace, profile, *, apply=False, check_running=None):
    from ..backup import wine_processes_running
    running = check_running or wine_processes_running
    if apply and running():
        raise ManagerError("Exit Windows Steam and all Wine bottles before editing native rendering.")
    path, original, video = plan(profile)
    if not set(NATIVE_RENDERING).issubset(video):
        raise ManagerError("Native-rendering keys are missing; use the game's graphics menu.")
    changes = {key: {"before": video[key], "after": value} for key, value in NATIVE_RENDERING.items()}
    note = "Native 100% custom rendering; verify 1x in game after launch. Quality and output resolution are preserved."
    if not apply:
        return {"applied": False, "changes": changes, "note": note}
    return {**_write_changes(workspace, profile, path, original, NATIVE_RENDERING, changes, running), "note": note}


def rendering_snapshot(profile):
    """Allowlisted graphics values and a file hash, never account IDs or paths."""
    try:
        path, content, video = plan(profile)
        import hashlib
        keys = set(BALANCED_1080) | set(NATIVE_RENDERING) | {
            "setting.monitor_index", "setting.high_dpi", "setting.mat_vsync",
            "setting.r_citadel_antialiasing", "setting.r_citadel_ssao_quality",
            "setting.r_citadel_shadow_quality", "setting.r_citadel_fog_quality",
            "setting.r_texture_stream_mip_bias", "setting.shaderquality",
            "setting.r_effects_bloom", "setting.r_post_bloom", "setting.r_depth_of_field",
            "setting.r_arealights", "setting.r_particle_depth_feathering", "setting.r_low_latency"}
        settings = {key: video[key] for key in sorted(keys) if key in video}
        result = {"available": True, "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                  "settings": settings, "scope": "Saved configuration; verify actual rendering in game."}
        fps_path = no_symlinks(path.with_name("machine_convars.vcfg"))
        if fps_path.is_file() and fps_path.stat().st_size <= 256 * 1024:
            config = parse_vdf(fps_path.read_text()).get("config")
            fps = config.get("convars") if isinstance(config, dict) else None
            if not isinstance(fps, dict):
                fps = {}
            result["fps_limits"] = {key: fps[key] for key in ("fps_max", "fps_max_ui")
                                    if isinstance(fps.get(key), str) and fps[key].isdigit()}
        return result
    except (ManagerError, OSError, UnicodeError):
        return {"available": False, "reason": "Saved graphics configuration is unavailable or unrecognized."}


def video_file(profile):
    from . import require_deadlock
    require_deadlock(profile, "Graphics editing")
    base = steam_path(profile).parent
    matches = list((base / "userdata").glob("*/1422450/local/cfg/video.txt"))
    if len(matches) != 1:
        raise ManagerError("Expected exactly one Deadlock video configuration. Start the game once, or configure graphics in game when multiple accounts exist.")
    return no_symlinks(matches[0])


def sdl_path(profile):
    from . import require_deadlock
    require_deadlock(profile, "SDL display mapping")
    path = no_symlinks(steam_path(profile).parent / "steamapps/common/Deadlock/game/bin/win64/SDL3.dll")
    if not path.is_file():
        raise ManagerError("Install Deadlock in the default Steam library before preparing a display.")
    return path


def plan(profile):
    path = video_file(profile)
    if path.stat().st_size > 256 * 1024:
        raise ManagerError("Unexpectedly large video configuration.")
    content = path.read_bytes().decode("utf-8")
    value = parse_vdf(content)
    video = value.get("video.cfg")
    if not isinstance(video, dict) or video.get("Version") != "20" or any(not isinstance(v, str) for v in video.values()):
        raise ManagerError("Untested video configuration schema; use Deadlock's graphics menu.")
    if not set(BALANCED_1080).issubset(video):
        raise ManagerError("Expected resolution settings are missing; use the game's graphics menu.")
    return path, content, video


def configure(workspace, profile, *, apply=False, check_running=None, mode="fullscreen", width=1920, height=1080, monitor_index=None):
    from ..backup import wine_processes_running
    if mode not in ("fullscreen", "borderless") or type(width) is not int or type(height) is not int or not (640 <= width <= 7680 and 480 <= height <= 4320):
        raise ManagerError("Choose fullscreen/borderless and a supported display size (640–7680 by 480–4320).")
    settings = {**BALANCED_1080, "setting.defaultres": str(width), "setting.defaultresheight": str(height),
                "setting.fullscreen": "1" if mode == "fullscreen" else "0",
                "setting.nowindowborder": "0" if mode == "fullscreen" else "1"}
    if apply and (check_running or wine_processes_running)():
        raise ManagerError("Exit Windows Steam and all Wine bottles before editing graphics settings.")
    path, original, video = plan(profile)
    if monitor_index is not None:
        if type(monitor_index) is not int or not 0 <= monitor_index < 32 or "setting.monitor_index" not in video:
            raise ManagerError("Invalid or unsupported game monitor index; no graphics settings were changed.")
        settings["setting.monitor_index"] = str(monitor_index)
    changes = {key: {"before": video[key], "after": value} for key, value in settings.items()}
    if not apply:
        return {"applied": False, "changes": changes, "note": "Only output resolution/display mode change; existing render scale and quality are preserved."}
    result = _write_changes(workspace, profile, path, original, settings, changes,
                            check_running or wine_processes_running)
    return {**result, "note": "Confirm display mode, resolution and render scale in the game. Steam Cloud decisions remain manual."}


def configure_fps(workspace, profile, *, cap=60, menu_cap=60, apply=False, check_running=None):
    from ..backup import wine_processes_running
    if any(type(value) is not int or not 30 <= value <= 360 for value in (cap, menu_cap)):
        raise ManagerError("Game and menu FPS limits must be integers from 30 to 360.")
    running = check_running or wine_processes_running
    if apply and running():
        raise ManagerError("Exit Windows Steam and all Wine bottles before editing game FPS limits.")
    path = no_symlinks(video_file(profile).with_name("machine_convars.vcfg"))
    if path.stat().st_size > 256 * 1024:
        raise ManagerError("Unexpectedly large game variable configuration.")
    original = path.read_bytes().decode("utf-8")
    config = parse_vdf(original).get("config")
    values = config.get("convars") if isinstance(config, dict) else None
    keys = ("fps_max", "fps_max_ui")
    if not isinstance(values, dict) or any(not isinstance(values.get(key), str) or not values[key].isdigit() for key in keys):
        raise ManagerError("Untested game FPS configuration; use Deadlock's settings menu.")
    settings = {"fps_max": str(cap), "fps_max_ui": str(menu_cap)}
    changes = {key: {"before": values[key], "after": value} for key, value in settings.items()}
    if not apply:
        return {"applied": False, "changes": changes}
    result = _write_changes(workspace, profile, path, original, settings, changes, running)
    return {**result, "note": "Saved game/menu limits; verify both in Deadlock after restart. These limits do not guarantee a minimum FPS."}


def _write_changes(workspace, profile, path, original, settings, changes, running):
    # Replace only selected values and retain original line endings/other keys.
    import re
    modified = original
    for key, value in settings.items():
        modified, count = re.subn(r'("' + re.escape(key) + r'"\s+")[^"]*(")',
                                  lambda m: m.group(1) + value + m.group(2), modified)
        if count != 1:
            raise ManagerError("Ambiguous graphics key; original configuration was preserved.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = private_dir(Path(workspace) / "DeadlockData/settings-backups" / profile["id"] / stamp)
    with (backup / path.name).open("xb") as stream:
        stream.write(original.encode("utf-8"))
    (backup / path.name).chmod(0o600)
    atomic_json(backup / "receipt.json", {"schema": 1, "file": str(path.relative_to(Path(profile["prefix"]))),
                                         "before_sha256": sha256(path), "changes": changes})
    if running() or path.read_bytes() != original.encode("utf-8"):
        raise ManagerError("Wine started or configuration changed during preparation; retry with Steam closed.")
    fd, temporary = tempfile.mkstemp(prefix=".video-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(modified.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {"applied": True, "changes": changes, "backup": str(backup)}


def data_roots(steam):
    """Local backups include only Deadlock's per-account data and local game config."""
    roots = []
    userdata = steam.parent / "userdata"
    if userdata.is_dir():
        for account in sorted(userdata.iterdir()):
            game = account / "1422450"
            if account.name.isdigit() and game.is_dir():
                roots.append(game)
    manifest = steam.parent / "steamapps/appmanifest_1422450.acf"
    if manifest.exists():
        if manifest.stat().st_size > 1024 * 1024:
            raise ManagerError("Unexpectedly large Steam manifest.")
        state = parse_vdf(manifest.read_text(encoding="utf-8-sig")).get("AppState", {})
        name = state.get("installdir") if isinstance(state, dict) else None
        if name and isinstance(name, str) and Path(name).name == name and name not in (".", ".."):
            config = steam.parent / "steamapps/common" / name / "game/citadel/cfg"
            if config.is_dir():
                roots.append(config)
    return roots
