"""Runtime adapters. Steam owns the account, game updates and game launch."""
import os
from pathlib import Path
import plistlib
import subprocess
import json

from .storage import ManagerError, identifier, no_symlinks

APP_ID = "1422450"
URIS = {"steam": "steam://open/main", "steam-big-picture": "steam://open/gamepadui",
        "install": f"steam://install/{APP_ID}",
        "launch": f"steam://rungameid/{APP_ID}"}


def clean_env():
    # Do not pass agent credentials, loader overrides or another bottle's env.
    allowed = ("HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL", "DISPLAY")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    return env


def validate_profile(profile, workspace):
    required = {"id", "provider", "runtime", "prefix", "graphics", "schema"}
    if not isinstance(profile, dict) or not required.issubset(profile) or profile["schema"] != 1:
        raise ManagerError("Invalid profile schema.")
    identifier(profile["id"])
    if profile["provider"] not in ("wine", "crossover"):
        raise ManagerError("Unsupported runtime provider.")
    if profile["graphics"] not in ("dxmt", "vendor"):
        raise ManagerError("Unsupported graphics mode.")
    for key in ("runtime", "prefix"):
        if not isinstance(profile[key], str) or not Path(profile[key]).is_absolute():
            raise ManagerError(f"{key} must be an absolute path.")
    expected = Path(workspace) / "Bottles" / profile["id"]
    no_symlinks(expected)
    if ":" in str(workspace):
        raise ManagerError("Wine library paths cannot use a workspace name containing a colon.")
    if Path(profile["prefix"]) != expected or expected.is_symlink():
        raise ManagerError("Each profile must own its named bottle inside this workspace.")
    if profile["provider"] == "wine":
        if profile.get("wine_family", "sikarugir") not in ("sikarugir", "highball"):
            raise ManagerError("Unsupported Wine family.")
        if profile["graphics"] != "dxmt" or not isinstance(profile.get("dxmt"), str):
            raise ManagerError("The free Wine profile requires an explicit DXMT runtime.")
        if not Path(profile["dxmt"]).is_absolute():
            raise ManagerError("DXMT path must be absolute.")
        if not isinstance(profile.get("support"), str) or not Path(profile["support"]).is_absolute():
            raise ManagerError("Wine support-library path must be absolute.")
    return profile


def steam_path(profile):
    prefix = Path(profile["prefix"])
    paths = [prefix / "drive_c/Program Files (x86)/Steam/steam.exe",
             prefix / "drive_c/Program Files/Steam/steam.exe"]
    for path in paths:
        if path.is_file() and path.resolve().is_relative_to(prefix.resolve()):
            return path
    raise ManagerError("Windows Steam is not installed in this profile. Run setup first.")


def verify_crossover(app):
    app = Path(app)
    try:
        with (app / "Contents/Info.plist").open("rb") as f:
            info = plistlib.load(f)
        if info.get("CFBundleIdentifier") != "com.codeweavers.CrossOver":
            raise ManagerError("Not an official CrossOver app bundle.")
        for args in (("--verify", "--deep", "--strict"), ("-d", "--verbose=2")):
            result = subprocess.run(["/usr/bin/codesign", *args, str(app)],
                                    capture_output=True, text=True, timeout=90, env=clean_env())
            if result.returncode:
                raise ManagerError("CrossOver signature verification failed.")
        if "TeamIdentifier=9C6B7X7Z8E" not in result.stderr.splitlines():
            raise ManagerError("CrossOver is not signed by the expected CodeWeavers identity.")
        return info.get("CFBundleShortVersionString", "unknown")
    except (OSError, ValueError, plistlib.InvalidFileException) as exc:
        raise ManagerError("Could not inspect the CrossOver app bundle.") from exc


def wine_binary(profile):
    root = Path(profile["runtime"])
    for name in ("wine", "wine64"):
        candidate = root / "bin" / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise ManagerError("Wine executable is missing from the registered runtime.")


def environment(profile, tuning=None):
    env = clean_env()
    env["WINEPREFIX"] = profile["prefix"]
    env["WINEDEBUG"] = "-all,err+all"
    if profile["provider"] == "wine":
        # Every process joining a wineserver must use the same synchronization
        # mode, including Exit, display probes, wineboot and diagnostics. These
        # helpers do not inherit game-only HUD/frame-pacing settings.
        from .performance import DEFAULTS, load, variables, validate_for_profile
        if tuning is None:
            workspace = Path(profile["prefix"]).parent.parent
            saved = load(workspace, profile["id"])
            tuning = dict(DEFAULTS, sync=saved["sync"])
        validate_for_profile(tuning, profile)
        root = Path(profile["runtime"])
        dxmt = Path(profile["dxmt"])
        support = Path(profile["support"])
        if not (support / "libinotify.0.dylib").is_file():
            raise ManagerError("Wine support libraries are missing; run runtime-install.")
        if not (dxmt / "x86_64-unix/winemetal.so").is_file():
            raise ManagerError("DXMT runtime is missing; run runtime-install.")
        env["PATH"] = str(root / "bin") + ":" + env["PATH"]
        # This engine's wineserver uses @rpath dependencies without LC_RPATH.
        # Supply only its own bundled library directory to the child process.
        gst = support / "GStreamer.framework/Versions/1.0"
        env["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join((str(support), str(gst / "lib"), str(root / "lib/wine/x86_64-unix"),
                                                    str(dxmt / "x86_64-unix"), "/usr/lib"))
        from .media_runtime import library_directory
        media = library_directory(profile)
        if media is not None:
            env['DYLD_FALLBACK_LIBRARY_PATH'] = str(media) + ':' + env['DYLD_FALLBACK_LIBRARY_PATH']
        env["DYLD_FALLBACK_FRAMEWORK_PATH"] = str(support) + ":/System/Library/Frameworks"
        if gst.is_dir():
            env["GST_PLUGIN_PATH"] = str(gst / "lib/gstreamer-1.0")
        env["WINEDLLPATH"] = str(dxmt) + ":" + str(root / "lib/wine")
        if profile.get("wine_family", "sikarugir") == "sikarugir":
            env["WINEDLLPATH_DXMT"] = str(dxmt)
            # Required by the Sikarugir Wine 11 host integration. It is not a
            # license key; this engine has no trial or payment step.
            env["SikarugirAppWine11"] = "1"
        else:
            env["WINEDLLPATH_PREPEND"] = str(dxmt)
            # Only the paired Highball Wine/DXMT builds support remote layers.
            env["DXMT_ALLOW_CROSS_PROCESS_SWAPCHAIN"] = "1"
        env["WINEDLLOVERRIDES"] = "d3d10core,d3d11,dxgi,winemetal=b"
        from .hotfix import active
        overlay = active(profile)
        if overlay:
            env["WINEDLLPATH_PREPEND"] = str(overlay) + ":" + env["WINEDLLPATH_PREPEND"]
        env.update(variables(tuning))
    return env


def launch_command(profile, action):
    if action not in URIS:
        raise ManagerError("Unsupported Steam action.")
    steam = steam_path(profile)
    if profile["provider"] == "crossover":
        cxstart = Path(profile["runtime"]) / "Contents/SharedSupport/CrossOver/bin/cxstart"
        if not cxstart.is_file():
            raise ManagerError("CrossOver cxstart is missing.")
        return [str(cxstart), "--bottle", profile["prefix"], URIS[action]]
    # Steam receives its normal protocol URL. Deadlock.exe is never invoked directly.
    # The current gamepadui URI also switches a running client. The startup flag
    # and legacy open/bigpicture URI did not switch the inspected desktop client.
    return [str(wine_binary(profile)), str(steam), URIS[action]]


def steam_control_command(profile, action):
    """Ask the selected Windows Steam client to stop its app or shut down normally."""
    if action not in ("game", "steam"):
        raise ManagerError("Unsupported Steam shutdown action.")
    # app_stop's explicit 0 means non-forced. -ifrunning avoids starting a client
    # if it exits between process inspection and delivery of this command.
    arguments = [str(steam_path(profile)), "-ifrunning"]
    arguments += ["+app_stop", APP_ID, "0"] if action == "game" else ["-shutdown"]
    if profile["provider"] == "crossover":
        cxstart = Path(profile["runtime"]) / "Contents/SharedSupport/CrossOver/bin/cxstart"
        if not cxstart.is_file():
            raise ManagerError("CrossOver cxstart is missing.")
        return [str(cxstart), "--bottle", profile["prefix"], *arguments]
    return [str(wine_binary(profile)), *arguments]


def exit_command(profile):
    return steam_control_command(profile, "game")


def start(profile, action, log, tuning=None):
    command = launch_command(profile, action)
    env = environment(profile, tuning)
    if profile["provider"] == "crossover":
        verify_crossover(profile["runtime"])
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        header = {"profile": profile["id"], "action": action,
                  "runtime": profile.get("runtime_version"), "dxmt": profile.get("dxmt_version"),
                  "performance_requested": tuning,
                  # Requested environment, not proof of a previously started server's mode.
                  "sync_environment": {key: env.get(key) for key in ("WINEMSYNC", "WINEESYNC")}}
        from .hotfix import status
        header["wine_hotfix"] = status(profile)
        stream.write(("# manager " + json.dumps(header) + "\n").encode())
        stream.flush()
        process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                   stdout=stream, stderr=subprocess.STDOUT,
                                   cwd=profile["prefix"], start_new_session=True)
        try:
            code = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        else:
            if code:
                raise ManagerError(f"Runtime exited immediately with code {code}. Inspect private log: {log}")
    return process.pid
