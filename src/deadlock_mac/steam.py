"""Read only narrowly scoped Steam metadata, never loginusers.vdf or credentials."""
from pathlib import Path
import re

from .storage import ManagerError


def parse_vdf(text):
    tokens = []
    pattern = re.compile(r'\s+|//[^\n]*|"((?:[^"\\]|\\.)*)"|([{}])')
    pos = 0
    while pos < len(text):
        match = pattern.match(text, pos)
        if not match:
            raise ManagerError("Malformed Steam manifest.")
        pos = match.end()
        if match.group(1) is not None:
            tokens.append(("text", re.sub(r'\\(["\\])', r'\1', match.group(1))))
        elif match.group(2):
            tokens.append((match.group(2), match.group(2)))
    index = 0

    def object_(nested=False, depth=0):
        nonlocal index
        if depth > 16:
            raise ManagerError("Steam manifest nesting exceeds the limit.")
        result = {}
        while index < len(tokens):
            kind, key = tokens[index]
            index += 1
            if kind == "}" and nested:
                return result
            if kind != "text" or index >= len(tokens) or key in result:
                raise ManagerError("Malformed or duplicate Steam manifest key.")
            kind, value = tokens[index]
            index += 1
            if kind == "{":
                value = object_(True, depth + 1)
            elif kind != "text":
                raise ManagerError("Malformed Steam manifest value.")
            result[key] = value
        if nested:
            raise ManagerError("Incomplete Steam manifest.")
        return result

    return object_()


def game_status(steam):
    manifest = steam.parent / "steamapps/appmanifest_1422450.acf"
    if not manifest.exists():
        return {"installed": False, "cloud": "unverified", "multiplayer": "untested"}
    if manifest.stat().st_size > 1024 * 1024:
        raise ManagerError("Unexpectedly large Steam manifest.")
    state = parse_vdf(manifest.read_text(encoding="utf-8-sig")).get("AppState", {})
    if not isinstance(state, dict) or state.get("appid") != "1422450":
        raise ManagerError("Manifest is not Deadlock's app manifest.")
    # Steam creates the manifest before downloading. Do not call that installed.
    # FullyInstalled is bit 4; this is still not proof of launch or file integrity.
    flags = state.get("StateFlags", "0")
    if not isinstance(flags, str) or not flags.isdigit():
        raise ManagerError("Invalid installation state in Steam manifest.")
    return {"installed": bool(int(flags) & 4), "manifest_present": True,
            "build_id": state.get("buildid", "unknown"),
            "state_flags": state.get("StateFlags", "unknown"),
            "bytes_downloaded": state.get("BytesDownloaded", "unknown"),
            "bytes_to_download": state.get("BytesToDownload", "unknown"),
            "cloud": "unverified", "multiplayer": "untested"}


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
