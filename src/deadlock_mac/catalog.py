"""Versioned runtime combinations, separate from provider implementation."""
import json
from pathlib import Path

from .storage import ManagerError, identifier

REPO = Path(__file__).resolve().parents[2]


def artifacts():
    return json.loads((REPO / "config/runtime-lock.json").read_text())["artifacts"]


def catalog():
    value = json.loads((REPO / "config/runtimes.json").read_text())
    known = artifacts()
    if not isinstance(value, dict) or value.get("schema") != 1 or not isinstance(value.get("runtimes"), dict):
        raise ManagerError("Invalid runtime catalog schema.")
    for name, entry in value["runtimes"].items():
        identifier(name)
        if not isinstance(entry, dict):
            raise ManagerError(f"Invalid runtime catalog entry: {name}")
        if entry.get("wine_family") not in ("highball", "sikarugir"):
            raise ManagerError(f"Unknown Wine adapter in runtime catalog: {name}")
        for role in ("wine", "dxmt", "support"):
            if entry.get(role) not in known:
                raise ManagerError(f"Runtime {name} references an unknown {role} artifact.")
        minimum = entry.get("minimum_macos")
        if not isinstance(minimum, list) or len(minimum) != 2 or not all(type(n) is int and n >= 0 for n in minimum):
            raise ManagerError(f"Invalid minimum macOS version for {name}.")
    if value.get("default") not in value["runtimes"]:
        raise ManagerError("Default runtime is missing from catalog.")
    return value


def runtime_set(name):
    try:
        return catalog()["runtimes"][name]
    except KeyError as exc:
        raise ManagerError(f"Unknown runtime set: {name}") from exc


def components(name):
    entry = runtime_set(name)
    return tuple(entry[role] for role in ("wine", "dxmt", "support"))
