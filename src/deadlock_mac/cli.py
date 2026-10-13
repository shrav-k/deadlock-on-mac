"""Small explicit commands for installing, inspecting and comparing runtimes."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.error

from . import __version__
from .backup import snapshot, wine_processes_running
from .catalog import REPO, artifacts, catalog, components, runtime_set
from .diagnostics import engine_dependencies, power_status
from . import performance
from . import game_settings
from . import game_mode
from .telemetry import summarize
from .runtime import (environment, launch_command, start, steam_path, validate_profile,
                      verify_crossover, wine_binary)
from .steam import game_status
from .storage import (ManagerError, atomic_json, download, identifier, lock, private_dir,
                      sha256, unpack, verify_extracted)

def fetch(workspace, name):
    artifact = artifacts()[name]
    return download(artifact["url"], artifact["sha256"], workspace / "Downloads" / artifact["filename"])


def install_runtimes(workspace, family="highball"):
    for name in components(family):
        artifact = artifacts()[name]
        destination = workspace / "Runtimes" / name
        receipt = destination / "manager-receipt.json"
        if destination.exists():
            if not receipt.is_file() or json.loads(receipt.read_text()).get("archive_sha256") != artifact["sha256"]:
                raise ManagerError(f"Unregistered runtime already exists at {destination}; use another workspace or inspect it.")
            print(f"Already installed: {name}")
            continue
        print(f"Downloading and verifying {name}…", flush=True)
        archive = fetch(workspace, name)
        unpack(archive, destination, include=artifact.get("include"), exclude=artifact.get("exclude", ()))
        atomic_json(receipt, {"schema": 1, "artifact": name, "archive_sha256": artifact["sha256"],
                              "url": artifact["url"], "installed_utc": timestamp()})
        print(f"Installed: {destination}")


def verify_runtimes(workspace, family):
    for name in components(family):
        artifact = artifacts()[name]
        archive = fetch(workspace, name)
        count = verify_extracted(archive, workspace / "Runtimes" / name,
                                 include=artifact.get("include"), exclude=artifact.get("exclude", ()))
        print(f"Verified {name}: {count} files/links match the pinned archive.")


def timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def profile_file(workspace, name):
    return workspace / "DeadlockData/profiles" / (identifier(name) + ".json")


def load_profile(workspace, name):
    path = profile_file(workspace, name)
    if not path.is_file() or path.is_symlink():
        raise ManagerError("Profile not found. Run profile-create first.")
    return validate_profile(json.loads(path.read_text()), workspace)


def create_profile(workspace, name, crossover=None, family="highball"):
    path = profile_file(workspace, name)
    if path.exists():
        raise ManagerError("Profile already exists. Use a new ID to test another runtime; existing data is preserved.")
    prefix = workspace / "Bottles" / name
    profile = {"schema": 1, "id": name, "prefix": str(prefix)}
    if crossover:
        version = verify_crossover(crossover)
        profile.update(provider="crossover", runtime=str(Path(crossover).absolute()),
                       graphics="vendor", runtime_version=version)
    else:
        wine_name, dxmt_name, support_name = components(family)
        candidate = runtime_set(family)
        profile.update(provider="wine", wine_family=candidate["wine_family"], runtime_set=family,
                       runtime=str(workspace / "Runtimes" / wine_name / artifacts()[wine_name]["root"]),
                       dxmt=str(workspace / "Runtimes" / dxmt_name / artifacts()[dxmt_name]["root"]), graphics="dxmt",
                       support=str(workspace / "Runtimes" / support_name / artifacts()[support_name]["root"]),
                       runtime_version=wine_name, dxmt_version=dxmt_name)
    validate_profile(profile, workspace)
    atomic_json(path, profile)
    print(f"Created {name}. Its dedicated Steam environment is {prefix}.")


def preflight(workspace, family):
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ManagerError("The free runtime is currently intended for Apple Silicon macOS.")
    minimum = tuple(runtime_set(family)["minimum_macos"])
    version = tuple(int(v) for v in platform.mac_ver()[0].split(".")[:2])
    if version < minimum:
        raise ManagerError(f"This runtime requires macOS {minimum[0]}.{minimum[1]} or newer.")
    if shutil.disk_usage(workspace).free < 80 * 1024**3:
        raise ManagerError("Keep at least 80 GiB free for setup and game updates.")
    result = subprocess.run(["/usr/bin/arch", "-x86_64", "/usr/bin/true"], capture_output=True, timeout=15)
    if result.returncode:
        raise ManagerError("Rosetta 2 is required. Install it using macOS's normal installation flow, then retry.")


def setup(workspace, profile):
    if profile["provider"] == "crossover":
        raise ManagerError("Install Steam using CrossOver's built-in Steam recipe into this profile's bottle; see docs/INSTALL.md.")
    preflight(workspace, profile.get("runtime_set", profile.get("wine_family", "sikarugir")))
    if wine_processes_running():
        raise ManagerError("Exit Windows Steam and all Wine bottles before setup; an active environment cannot be reinitialized.")
    wine = wine_binary(profile)
    env = environment(profile)
    prefix = private_dir(profile["prefix"])
    logs = private_dir(workspace / "DeadlockData/logs" / profile["id"])
    logfile = logs / f"setup-{timestamp()}.log"
    fd = os.open(logfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        print("Initializing the Wine environment…", flush=True)
        subprocess.run([str(wine), "wineboot", "-u"], env=env, cwd=prefix,
                       stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=180)
        try:
            steam_path(profile)
        except ManagerError:
            installer = fetch(workspace, "steam-setup")
            print("Installing Valve's Windows Steam client…", flush=True)
            subprocess.run([str(wine), str(installer), "/S"], env=env, cwd=prefix,
                           stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=240)
    steam_path(profile)
    print(f"Steam is installed. Run steam and sign into your existing account. Setup log: {logfile}")


def bootstrap(workspace, name, family):
    preflight(workspace, family)
    if wine_processes_running():
        raise ManagerError("Exit Windows Steam and all Wine bottles before setup. Use Open Steam or Play for an existing installation.")
    path = profile_file(workspace, name)
    if path.exists():
        profile = load_profile(workspace, name)
        if profile.get("runtime_set") != family:
            raise ManagerError("Existing profile uses another runtime; choose a new profile ID.")
    install_runtimes(workspace, family)
    if not path.exists():
        create_profile(workspace, name, family=family)
    setup(workspace, load_profile(workspace, name))


def doctor(workspace, profile):
    result = {"manager_version": __version__, "system": platform.system(),
              "macos": platform.mac_ver()[0], "architecture": platform.machine(),
              "free_gib": round(shutil.disk_usage(workspace).free / 1024**3),
              "provider": profile["provider"], "runtime_version": profile.get("runtime_version"),
              "graphics_requested": profile["graphics"], "graphics_verified_in_game": False,
              "bottle_exists": Path(profile["prefix"]).is_dir(),
              "steam_account": "Sign in and verify in Steam; credentials are not inspected."}
    result["power"] = power_status()
    result["performance_requested"] = performance.load(workspace, profile["id"])
    try:
        steam = steam_path(profile)
        result["steam_installed"] = True
    except ManagerError as exc:
        result["steam_installed"] = False
        result["note"] = str(exc)
    else:
        try:
            result["game"] = game_status(steam)
        except ManagerError as exc:
            result["game_metadata_error"] = str(exc)
    if profile["provider"] == "wine":
        result["runtime_present"] = (Path(profile["runtime"]) / "bin").is_dir()
        result["dxmt_version"] = profile.get("dxmt_version")
    else:
        result["runtime_present"] = Path(profile["runtime"]).is_dir()
    return result


def main(argv=None):
    try:
        runtime_catalog = catalog()
    except (ManagerError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Error loading runtime catalog: {exc}", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(description="Run Deadlock through your Steam account on macOS.")
    parser.add_argument("--workspace", type=Path, default=REPO.parent,
                        help="Deadlock workspace folder; runtimes, bottles and private state live here")
    parser.add_argument("--profile", default=runtime_catalog["default"])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("bootstrap", help="Check the Mac, install pinned runtimes and set up Windows Steam")
    p.add_argument("--runtime", choices=runtime_catalog["runtimes"], default=runtime_catalog["default"])
    p = sub.add_parser("runtime-install", help="Download and verify a pinned free Wine + DXMT pair")
    p.add_argument("--runtime", choices=runtime_catalog["runtimes"], default=runtime_catalog["default"])
    p = sub.add_parser("runtime-verify", help="Check installed runtime files against pinned archives")
    p.add_argument("--runtime", choices=runtime_catalog["runtimes"], default=runtime_catalog["default"])
    p = sub.add_parser("profile-create", help="Create an immutable runtime profile")
    p.add_argument("--crossover", type=Path, help="Optional official CrossOver.app for comparison")
    p.add_argument("--runtime", choices=runtime_catalog["runtimes"], default=runtime_catalog["default"])
    sub.add_parser("runtimes", help="List available runtime combinations and known compatibility limits")
    sub.add_parser("setup", help="Initialize the free profile and install Windows Steam")
    for action in ("steam", "install", "launch"):
        p = sub.add_parser(action)
        p.add_argument("--dry-run", action="store_true", help="Print argv without executing anything")
    sub.add_parser("doctor", help="Print a shareable allowlisted report; never reads Steam credentials")
    sub.add_parser("runtime-dependencies", help="Inspect direct Wine module imports for missing host libraries")
    sub.add_parser("backup", help="Snapshot Deadlock data while all Steam/Wine processes are closed")
    sub.add_parser("profiles", help="List configured runtime profiles")
    p = sub.add_parser("performance", help="Inspect or change reversible launch settings; Steam must be closed to change them")
    p.add_argument("--fps-cap", type=int)
    p.add_argument("--sync", choices=("auto", "none", "msync", "esync"))
    p.add_argument("--hud", choices=("on", "off"))
    p.add_argument("--hud-log", choices=("on", "off"))
    p.add_argument("--reset", action="store_true")
    p = sub.add_parser("graphics-preset", help="Preview a backed-up 1080p fullscreen edit; preserves quality and render scale")
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("performance-report", help="Summarize Metal HUD frame intervals for a game PID")
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--warmup-seconds", type=float, default=0)
    p.add_argument("--start-time", help="Local ISO time when the gameplay segment started (no UTC offset)")
    p.add_argument("--end-time", help="Exclusive local ISO end time, to exclude later menus or settings")
    p = sub.add_parser("game-mode", help="Optional Apple Game Mode status or bounded system-wide diagnostic test")
    p.add_argument("--tool", type=Path, help="Compatible Apple-signed gamepolicyctl; otherwise discover through Xcode")
    action = p.add_mutually_exclusive_group()
    action.add_argument("--test", action="store_true", help="Find the one running Deadlock process and start a bounded test")
    action.add_argument("--test-pid", type=int, help="Native deadlock.exe PID; temporarily force Game Mode on")
    action.add_argument("--restore", action="store_true", help="Recover the previous automatic policy after an interrupted test")
    p.add_argument("--seconds", type=int, default=300, help="Test duration, at most 900 seconds")
    args = parser.parse_args(argv)
    workspace = args.workspace.expanduser().resolve()
    try:
        identifier(args.profile)
        if sys.version_info < (3, 12):
            raise ManagerError("Python 3.12 or newer is required for safe archive extraction.")
        if args.command == "bootstrap" and not workspace.exists():
            private_dir(workspace)
        if not workspace.is_dir():
            raise ManagerError("Workspace must be an existing directory.")
        if args.command == "runtimes":
            for name, entry in runtime_catalog["runtimes"].items():
                print(f"{name}: {entry['label']} — {entry['status']}")
            return 0
        if args.command == "performance-report":
            with args.log.open() as stream:
                print(json.dumps(summarize(stream, args.pid, args.warmup_seconds,
                                           args.start_time, args.end_time), indent=2))
            return 0
        if args.command == "game-mode":
            tool = game_mode.AppleTool(args.tool)
            if args.test_pid is None and not args.test and not args.restore:
                print(json.dumps(tool.status(), indent=2))
                return 0
            with lock(workspace / "DeadlockData"):
                receipt = workspace / "DeadlockData/game-mode-test.json"
                if args.restore:
                    print(json.dumps(game_mode.restore(tool, receipt), indent=2))
                else:
                    pid = game_mode.find_game() if args.test else args.test_pid
                    game_mode.trial(tool, pid, args.seconds, receipt,
                                    report=lambda message: print(message, flush=True))
            return 0
        if args.command == "profiles":
            folder = workspace / "DeadlockData/profiles"
            for path in sorted(folder.glob("*.json")):
                profile = load_profile(workspace, path.stem)
                print(f"{profile['id']}: {profile['provider']} / {profile.get('runtime_version', 'unknown')}")
            return 0
        if args.command in ("doctor", "runtime-dependencies", "steam", "install", "launch", "setup", "backup", "performance", "graphics-preset"):
            profile = load_profile(workspace, args.profile)
        if args.command == "runtime-dependencies":
            result = engine_dependencies(profile)
            print(json.dumps(result, indent=2))
            return 1 if result["unresolved"] else 0
        if args.command == "doctor":
            print(json.dumps(doctor(workspace, profile), indent=2))
            return 0
        if getattr(args, "dry_run", False):
            print(json.dumps({"argv": launch_command(profile, args.command),
                              "performance_requested": performance.load(workspace, profile["id"]),
                              "provider": profile["provider"], "executes": False}, indent=2))
            return 0
        with lock(workspace / "DeadlockData"):
            if args.command == "bootstrap":
                bootstrap(workspace, args.profile, args.runtime)
            elif args.command == "graphics-preset":
                print(json.dumps(game_settings.configure(workspace, profile, apply=args.apply), indent=2))
            elif args.command == "performance":
                settings = performance.load(workspace, args.profile)
                if args.reset:
                    settings = dict(performance.DEFAULTS)
                for key, value in (("fps_cap", args.fps_cap), ("sync", args.sync),
                                   ("metal_hud", None if args.hud is None else args.hud == "on"),
                                   ("hud_logging", None if args.hud_log is None else args.hud_log == "on")):
                    if value is not None:
                        settings[key] = value
                if args.reset or any(v is not None for v in (args.fps_cap, args.sync, args.hud, args.hud_log)):
                    performance.save(workspace, profile, settings)
                print(json.dumps(settings, indent=2))
            elif args.command == "runtime-install":
                install_runtimes(workspace, args.runtime)
            elif args.command == "runtime-verify":
                verify_runtimes(workspace, args.runtime)
            elif args.command == "profile-create":
                create_profile(workspace, args.profile, args.crossover, args.runtime)
            elif args.command == "setup":
                setup(workspace, profile)
            elif args.command == "backup":
                print(snapshot(profile, workspace / "DeadlockBackups"))
            else:
                logs = private_dir(workspace / "DeadlockData/logs" / args.profile)
                log = logs / f"{args.command}-{timestamp()}.log"
                tuning = performance.load(workspace, args.profile)
                pid = start(profile, args.command, log, tuning)
                print(f"Request sent to Windows Steam (launcher PID {pid}). Private log: {log}")
                print("Check Steam for login, updates or Cloud conflicts. This is not proof of a successful game launch.")
        return 0
    except (ManagerError, OSError, ValueError, tarfile.TarError, subprocess.SubprocessError,
            urllib.error.URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
