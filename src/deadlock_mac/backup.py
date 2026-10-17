"""Append-only local snapshots. No automatic restore or cloud conflict resolution."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import zipfile

from .runtime import clean_env, steam_path
from .steam import data_roots
from .storage import ManagerError, private_dir


def wine_processes_running():
    result = subprocess.run(["/bin/ps", "-axo", "comm="], capture_output=True,
                            text=True, timeout=15, env=clean_env())
    if result.returncode:
        raise ManagerError("Cannot check whether Steam/Wine is closed; operation refused.")
    # Conservative, read-only check across runtimes. No PID signalling, no command
    # lines or environment blocks stored in reports. Exit other bottles too.
    return any(re.search(r"(?i)(?:^|[/\\])(?:wine(?:64)?(?:-preloader)?|wineserver|steam\.exe|"
                         r"steamwebhelper\.exe|deadlock\.exe)$", line.strip())
               for line in result.stdout.splitlines())


def collect_files(steam):
    base = steam.parent
    files = []
    for root in data_roots(steam):
        if root.is_symlink() or not root.resolve().is_relative_to(base.resolve()):
            raise ManagerError("Refusing a save directory linked outside Steam.")
        for directory, dirs, names in os.walk(root, followlinks=False):
            for name in dirs + names:
                path = Path(directory) / name
                mode = path.lstat().st_mode
                if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                    raise ManagerError("Refusing symlinks or special files in game data.")
            for name in names:
                path = Path(directory) / name
                files.append((path, path.stat()))
    return sorted(files)


def snapshot(profile, destination, *, check_running=wine_processes_running):
    if check_running():
        raise ManagerError("Exit Steam and all Wine bottles before backing up. No processes were stopped.")
    steam = steam_path(profile)
    base = steam.parent
    files = collect_files(steam)
    if not files:
        raise ManagerError("No Deadlock data exists in this profile yet; no empty backup was created.")
    if sum(s.st_size for _, s in files) > 2 * 1024**3 or len(files) > 20000:
        raise ManagerError("Game data exceeds the 2 GiB / 20,000-file backup limit.")
    destination = private_dir(destination)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    final = destination / f"{profile['id']}-{timestamp}.zip"
    fd, partial = tempfile.mkstemp(prefix=".backup-", dir=destination)
    os.close(fd)
    try:
        inventory = {}
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, before in files:
                # O_NOFOLLOW protects the final component if it changes after the walk.
                source_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                name = str(path.relative_to(base))
                digest = hashlib.sha256()
                with os.fdopen(source_fd, "rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if (opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
                            before.st_ino, before.st_size, before.st_mtime_ns):
                        raise ManagerError("Game data changed during backup; retry with Steam closed.")
                    with archive.open(name, "w") as out:
                        while data := stream.read(1024 * 1024):
                            digest.update(data)
                            out.write(data)
                inventory[name] = digest.hexdigest()
            archive.writestr("backup-manifest.json", json.dumps({
                "schema": 1, "app_id": "1422450", "profile": profile["id"],
                "created_utc": timestamp, "files": inventory,
                "scope": "Deadlock userdata and game/citadel/cfg; not a full bottle backup"
            }, indent=2))
        after_files = collect_files(steam)
        if [p for p, _ in after_files] != [p for p, _ in files]:
            raise ManagerError("Game files appeared or disappeared during backup; snapshot was discarded.")
        for (_, before), (_, after) in zip(files, after_files):
            if (after.st_ino, after.st_size, after.st_mtime_ns) != (
                    before.st_ino, before.st_size, before.st_mtime_ns):
                raise ManagerError("Game data changed during backup; snapshot was discarded.")
        if check_running():
            raise ManagerError("Wine started during backup; snapshot was discarded.")
        os.link(partial, final)  # Never replace an existing backup, even on name collision.
        return final
    finally:
        Path(partial).unlink(missing_ok=True)
