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
from .backup import snapshot
from .runtime import (environment, launch_command, start, steam_path, validate_profile,
                      verify_crossover, wine_binary)
from .steam import game_status
from .storage import (ManagerError, atomic_json, download, identifier, lock, private_dir,
                      sha256, unpack, verify_extracted)

REPO = Path(__file__).resolve().parents[2]
WINE = "sikarugir-wine-11.0_1"
DXMT = "dxmt-0.80"
SUPPORT = "sikarugir-support-1.0.21"
RUNTIMES = {"sikarugir": (WINE, DXMT),
            "highball": ("highball-wine-20261006", "dxmt-highball-a444716")}


def artifacts():
    return json.loads((REPO / "config/runtime-lock.json").read_text())["artifacts"]


def fetch(workspace, name):
    artifact = artifacts()[name]
    return download(artifact["url"], artifact["sha256"], workspace / "Downloads" / artifact["filename"])


def install_runtimes(workspace, family="highball"):
    for name in (*RUNTIMES[family], SUPPORT):
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
    for name in (*RUNTIMES[family], SUPPORT):
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
        wine_name, dxmt_name = RUNTIMES[family]
        profile.update(provider="wine", wine_family=family,
                       runtime=str(workspace / "Runtimes" / wine_name / artifacts()[wine_name]["root"]),
                       dxmt=str(workspace / "Runtimes" / dxmt_name / artifacts()[dxmt_name]["root"]), graphics="dxmt",
                       support=str(workspace / "Runtimes" / SUPPORT / artifacts()[SUPPORT]["root"]),
                       runtime_version=wine_name, dxmt_version=dxmt_name)
    validate_profile(profile, workspace)
    atomic_json(path, profile)
    print(f"Created {name}. Its dedicated Steam environment is {prefix}.")


def setup(workspace, profile):
    if profile["provider"] == "crossover":
        raise ManagerError("Install Steam using CrossOver's built-in Steam recipe into this profile's bottle; see docs/INSTALL.md.")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ManagerError("The free runtime is currently intended for Apple Silicon macOS.")
    minimum = (15, 0) if profile.get("wine_family") == "highball" else (14, 6)
    version = tuple(int(v) for v in platform.mac_ver()[0].split(".")[:2])
    if version < minimum:
        raise ManagerError(f"This runtime requires macOS {minimum[0]}.{minimum[1]} or newer.")
    if shutil.disk_usage(workspace).free < 80 * 1024**3:
        raise ManagerError("Keep at least 80 GiB free for setup and game updates.")
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


def doctor(workspace, profile):
    result = {"manager_version": __version__, "system": platform.system(),
              "macos": platform.mac_ver()[0], "architecture": platform.machine(),
              "free_gib": round(shutil.disk_usage(workspace).free / 1024**3),
              "provider": profile["provider"], "runtime_version": profile.get("runtime_version"),
              "graphics_requested": profile["graphics"], "graphics_verified_in_game": False,
              "bottle_exists": Path(profile["prefix"]).is_dir(),
              "steam_account": "Sign in and verify in Steam; credentials are not inspected."}
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
    parser = argparse.ArgumentParser(description="Run Deadlock through your Steam account on macOS.")
    parser.add_argument("--workspace", type=Path, default=REPO.parent,
                        help="Deadlock workspace folder; runtimes, bottles and private state live here")
    parser.add_argument("--profile", default="highball")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("runtime-install", help="Download and verify a pinned free Wine + DXMT pair")
    p.add_argument("--runtime", choices=RUNTIMES, default="highball")
    p = sub.add_parser("runtime-verify", help="Check installed runtime files against pinned archives")
    p.add_argument("--runtime", choices=RUNTIMES, default="highball")
    p = sub.add_parser("profile-create", help="Create an immutable runtime profile")
    p.add_argument("--crossover", type=Path, help="Optional official CrossOver.app for comparison")
    p.add_argument("--runtime", choices=RUNTIMES, default="highball")
    sub.add_parser("setup", help="Initialize the free profile and install Windows Steam")
    for action in ("steam", "install", "launch"):
        p = sub.add_parser(action)
        p.add_argument("--dry-run", action="store_true", help="Print argv without executing anything")
    sub.add_parser("doctor", help="Print a shareable allowlisted report; never reads Steam credentials")
    sub.add_parser("backup", help="Snapshot Deadlock data while all Steam/Wine processes are closed")
    sub.add_parser("profiles", help="List configured runtime profiles")
    args = parser.parse_args(argv)
    workspace = args.workspace.expanduser().resolve()
    try:
        identifier(args.profile)
        if sys.version_info < (3, 12):
            raise ManagerError("Python 3.12 or newer is required for safe archive extraction.")
        if not workspace.is_dir():
            raise ManagerError("Workspace must be an existing directory.")
        if args.command == "profiles":
            folder = workspace / "DeadlockData/profiles"
            for path in sorted(folder.glob("*.json")):
                profile = load_profile(workspace, path.stem)
                print(f"{profile['id']}: {profile['provider']} / {profile.get('runtime_version', 'unknown')}")
            return 0
        if args.command in ("doctor", "steam", "install", "launch", "setup", "backup"):
            profile = load_profile(workspace, args.profile)
        if args.command == "doctor":
            print(json.dumps(doctor(workspace, profile), indent=2))
            return 0
        if getattr(args, "dry_run", False):
            print(json.dumps({"argv": launch_command(profile, args.command),
                              "provider": profile["provider"], "executes": False}, indent=2))
            return 0
        with lock(workspace / "DeadlockData"):
            if args.command == "runtime-install":
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
                pid = start(profile, args.command, log)
                print(f"Request sent to Windows Steam (launcher PID {pid}). Private log: {log}")
                print("Check Steam for login, updates or Cloud conflicts. This is not proof of a successful game launch.")
        return 0
    except (ManagerError, OSError, ValueError, tarfile.TarError, subprocess.SubprocessError,
            urllib.error.URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
