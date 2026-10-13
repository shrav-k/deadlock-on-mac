"""An explicit, hash-verified DLL overlay; original runtime files stay intact."""
import json
from pathlib import Path
import shutil
import tempfile

from .catalog import REPO
from .storage import ManagerError, atomic_json, no_symlinks, private_dir, sha256


def specification():
    return json.loads((REPO / "config/wine-hotfix.json").read_text())


def verify(directory, spec=None):
    spec = specification() if spec is None else spec
    directory = no_symlinks(directory)
    for name, digest in spec["files"].items():
        path = no_symlinks(directory / name)
        if not path.is_file() or sha256(path) != digest:
            raise ManagerError(f"Wine hotfix integrity check failed: {name}. Rebuild the pinned hotfix; no unverified DLL will be loaded.")
    return directory


def compatible(profile, spec):
    return (profile.get("provider") == "wine" and profile.get("wine_family") == "highball"
            and profile.get("runtime_version") == spec["runtime_version"])


def receipt(workspace, profile):
    return no_symlinks(Path(workspace) / "DeadlockData/hotfixes" / (profile["id"] + ".json"))


def active(profile):
    workspace = Path(profile["prefix"]).parents[1]
    path = receipt(workspace, profile)
    if not path.exists():
        return None
    state = json.loads(path.read_text())
    if not state.get("enabled"):
        return None
    spec = specification()
    if state.get("id") != spec["id"] or not compatible(profile, spec):
        raise ManagerError("Active Wine hotfix does not match this runtime. Disable it with Steam closed before changing runtimes.")
    return verify(workspace / "Runtimes" / spec["id"], spec)


def status(profile):
    directory = active(profile)
    return {"enabled": directory is not None, "id": specification()["id"] if directory else None,
            "verified": directory is not None}


def configure(workspace, profile, enabled):
    from .backup import wine_processes_running
    if wine_processes_running():
        raise ManagerError("Exit Windows Steam and all Wine bottles before changing the hotfix; running processes retain their DLL environment.")
    spec = specification()
    if enabled:
        if not compatible(profile, spec):
            raise ManagerError("This hotfix only supports the pinned Highball runtime.")
        verify(Path(workspace) / "Runtimes" / spec["id"], spec)
    atomic_json(receipt(workspace, profile), {"schema": 1, "id": spec["id"], "enabled": enabled})
    return status(profile)


def install_available(workspace, profile):
    """Fresh setup uses a reviewed local/bundled payload; preserve explicit rollback."""
    spec = specification()
    if not compatible(profile, spec):
        return False
    if receipt(workspace, profile).exists():
        return status(profile)["enabled"]
    target = Path(workspace) / "Runtimes" / spec["id"]
    if not target.exists():
        bundled = REPO / "runtime-overlays" / spec["id"]
        if not bundled.exists():
            return False
        verify(bundled, spec)
        private_dir(target.parent)
        with tempfile.TemporaryDirectory(prefix=".hotfix-", dir=target.parent) as temp:
            stage = Path(temp) / spec["id"]
            shutil.copytree(bundled, stage)
            verify(stage, spec)
            stage.rename(target)
    configure(workspace, profile, True)
    return True
