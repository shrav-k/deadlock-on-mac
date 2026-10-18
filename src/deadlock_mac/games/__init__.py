"""Versioned game definitions; only reviewed adapters may execute game-specific code."""
from dataclasses import asdict, dataclass
import json
from pathlib import PureWindowsPath
import re

from ..catalog import REPO
from ..storage import ManagerError, identifier

DEFAULT_GAME = "deadlock"


@dataclass(frozen=True)
class GameDefinition:
    id: str
    version: int
    title: str
    steam_app_id: str
    process_name: str
    install_directory: str
    launch_strategy: str
    graphics_api: str
    settings_adapter: str
    status: str
    hotfixes: bool

    def __post_init__(self):
        identifier(self.id)
        if type(self.version) is not int or self.version < 1:
            raise ManagerError("Invalid game recipe version.")
        if not isinstance(self.steam_app_id, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", self.steam_app_id):
            raise ManagerError("Invalid Steam app ID in game recipe.")
        if not isinstance(self.process_name, str) or not re.fullmatch(r"[a-z0-9_-]+\.exe", self.process_name):
            raise ManagerError("Invalid game process name.")
        if (not isinstance(self.install_directory, str) or not self.install_directory
                or self.install_directory in (".", "..") or "/" in self.install_directory
                or "\\" in self.install_directory or ":" in self.install_directory
                or PureWindowsPath(self.install_directory).is_absolute()):
            raise ManagerError("Invalid game installation directory.")
        if self.settings_adapter not in ("deadlock", "elden-ring-seamless"):
            raise ManagerError("Unknown reviewed game settings adapter.")
        if self.launch_strategy not in ("steam-uri", "seamless-launcher") or self.graphics_api not in ("d3d11", "d3d12"):
            raise ManagerError("Unknown game launch or graphics requirement.")
        if self.status not in ("experimental", "research") or type(self.hotfixes) is not bool:
            raise ManagerError("Invalid game qualification state.")
        if not isinstance(self.title, str) or not self.title.strip() or len(self.title) > 100:
            raise ManagerError("Invalid game title.")


def definitions():
    try:
        value = json.loads((REPO / "config/games.json").read_text())
        if type(value.get("schema")) is not int or value["schema"] != 1 or not isinstance(value.get("games"), dict):
            raise ManagerError("Invalid game catalog schema.")
        result = {name: GameDefinition(id=name, **fields) for name, fields in value["games"].items()}
        if DEFAULT_GAME not in result:
            raise ManagerError("Default game recipe is missing.")
        return result
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise ManagerError("Could not read the game catalog.") from exc


def get_game(name=DEFAULT_GAME):
    identifier(name)
    try:
        return definitions()[name]
    except KeyError as exc:
        raise ManagerError(f"Unknown game recipe: {name}") from exc


def for_profile(profile):
    # Legacy profiles and receipts retain their meaning without a disk migration.
    schema = profile.get("schema", 1)
    if type(schema) is not int:
        raise ManagerError("Invalid game profile schema.")
    if schema == 1:
        if "game_id" in profile or "game_recipe_version" in profile:
            raise ManagerError("Legacy profiles cannot be rebound to another game; create a new profile.")
        return get_game()
    if schema != 2 or "game_id" not in profile or "game_recipe_version" not in profile:
        raise ManagerError("A version 2 profile requires an explicit game binding.")
    game = get_game(profile["game_id"])
    if type(profile["game_recipe_version"]) is not int or profile["game_recipe_version"] != game.version:
        raise ManagerError("Game recipe version changed; an explicit tested migration is required.")
    return game


def from_receipt(state):
    if ("game_id" in state) != ("game_recipe_version" in state):
        raise ManagerError("Incomplete game binding in recovery receipt.")
    game = get_game(state.get("game_id", DEFAULT_GAME))
    version = state.get("game_recipe_version", game.version)
    if type(version) is not int or version != game.version:
        raise ManagerError("Unrecognized game recipe in recovery receipt.")
    return game


def binding(game):
    return {"game_id": game.id, "game_recipe_version": game.version}


def settings_adapter(profile):
    game = for_profile(profile)
    if game.settings_adapter == "deadlock":
        from . import deadlock
        return deadlock
    from . import elden_ring
    return elden_ring


def require_deadlock(profile, operation):
    if for_profile(profile).settings_adapter != "deadlock":
        raise ManagerError(f"{operation} has only been qualified for Deadlock; this game's files were left unchanged.")


def launch_blockers(game, profile):
    blockers = []
    if game.graphics_api == "d3d12" and profile.get("graphics") == "dxmt":
        blockers.append("Elden Ring requires DirectX 12; the configured DXMT renderer supports Direct3D 10/11.")
    if game.launch_strategy != "steam-uri":
        blockers.append("The Seamless Co-op/Mod Engine launch routes, version checks and normal exit are not yet qualified; no vanilla Steam launch fallback is allowed.")
    if game.status == "research":
        blockers.append("This game recipe is research-only. Qualify a separate runtime/profile before enabling Play.")
    return blockers


def require_launch(profile):
    game = for_profile(profile)
    blockers = launch_blockers(game, profile)
    if blockers:
        raise ManagerError(" ".join(blockers))
    return game


def describe(game, profile=None):
    return {**asdict(game), "launch_blockers": launch_blockers(game, profile or {"graphics": "dxmt"}),
            "settings_writable": game.settings_adapter == "deadlock"}
