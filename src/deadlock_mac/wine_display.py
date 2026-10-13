"""A narrow offline RetinaMode edit; never starts or stops a Wine process."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .storage import ManagerError, atomic_json, identifier, no_symlinks, private_dir

KEY = r"Software\\Wine\\Mac Driver"
VALUES = ("y", "n", "Y", "N", "1", "0", "true", "false", "yes", "no")


def read(profile):
    if profile["provider"] != "wine":
        raise ManagerError("Configure Retina support for the official CrossOver provider in CrossOver itself.")
    path = no_symlinks(Path(profile["prefix"]) / "user.reg")
    if path.stat().st_size > 32 * 1024**2:
        raise ManagerError("Unexpectedly large Wine user registry; no display edit was made.")
    data = path.read_bytes()
    text = data.decode("utf-8")
    if text.partition("\n")[0].rstrip("\r") != "WINE REGISTRY Version 2":
        raise ManagerError("Unsupported Wine registry format; no display edit was made.")
    headers = list(re.finditer(r"(?m)^\[([^\]\r\n]+)\][^\r\n]*", text))
    matches = [i for i, header in enumerate(headers) if header[1] == KEY]
    if len(matches) > 1:
        raise ManagerError("Duplicate Mac Driver registry sections; no display edit was made.")
    span, value, line = None, None, None
    if matches:
        i = matches[0]
        span = (headers[i].end(), headers[i+1].start() if i+1 < len(headers) else len(text))
        values = list(re.finditer(r'(?m)^"RetinaMode"[^\r\n]*', text[span[0]:span[1]]))
        if len(values) > 1:
            raise ManagerError("Duplicate RetinaMode values; no display edit was made.")
        if values:
            match = re.fullmatch(r'"RetinaMode"="([^"]*)"', values[0][0])
            if not match or match[1] not in VALUES:
                raise ManagerError("Unknown RetinaMode value/type; no display edit was made.")
            value = match[1]
            line = (span[0] + values[0].start(), span[0] + values[0].end())
    return path, data, text, span, line, value


def status(profile):
    value = read(profile)[-1]
    return {"value": value, "enabled": value is not None and value[0] in "yYtT1",
            "scope": "Saved Wine bottle setting; restart required. This is not live game resolution verification."}


def configure(workspace, profile, mode=None, *, apply=False, restore=None, check_running=None):
    from .backup import wine_processes_running
    if mode not in (None, "on", "off", "default") or (mode is not None and restore is not None):
        raise ManagerError("Choose one Retina setting or one backup to restore.")
    if mode is None and restore is None:
        if apply:
            raise ManagerError("Choose a Retina setting before applying it.")
        return status(profile)
    running = check_running or wine_processes_running
    if apply and running():
        raise ManagerError("Exit Windows Steam and all Wine bottles before changing Retina mode.")
    path, original, text, span, line, before = read(profile)
    backups = Path(workspace) / "DeadlockData/display-backups" / identifier(profile["id"])
    after = {"on": "y", "off": "n", "default": None}.get(mode)
    if restore is not None:
        receipt_path = no_symlinks(backups / identifier(restore) / "receipt.json")
        receipt = json.loads(receipt_path.read_text())
        if ("before" not in receipt or receipt.get("schema") != 1 or receipt.get("profile") != profile["id"] or
                receipt.get("setting") != "RetinaMode" or receipt.get("before") not in (*VALUES, None)):
            raise ManagerError("Invalid Retina backup receipt.")
        after = receipt["before"]
    result = {"applied": False, "before": before, "after": after,
              "note": "Changes Wine pixel reporting for the whole bottle, including Steam. Select borderless and verify resolution/input in game after restart."}
    if not apply or before == after:
        return result
    newline = "\r\n" if b"\r\n" in original else "\n"
    replacement = f'"RetinaMode"="{after}"' if after is not None else ""
    if line:
        modified = text[:line[0]] + replacement + text[line[1]:]
    elif span:
        modified = text[:span[0]] + newline + replacement + text[span[0]:]
    else:
        modified = text + newline + f"[{KEY}]" + newline + replacement + newline
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ").lower()
    backup = private_dir(backups / stamp)
    atomic_json(backup / "receipt.json", {"schema": 1, "profile": profile["id"], "setting": "RetinaMode",
                                        "before": before, "after": after,
                                        "registry_sha256_before": hashlib.sha256(original).hexdigest()})
    # Keep only the edited value in the backup, not Steam/account registry data.
    if running() or path.read_bytes() != original:
        raise ManagerError("Wine started or its registry changed; retry with Steam closed. No display edit was made.")
    fd, temporary = tempfile.mkstemp(prefix=".retina-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(modified.encode("utf-8")); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return {**result, "applied": True, "backup_id": stamp}
