"""An explicit, hash-verified DLL overlay; original runtime files stay intact."""
import json
from pathlib import Path
import shutil
import tempfile

from .catalog import REPO
from .games import for_profile
from .storage import ManagerError, atomic_json, no_symlinks, private_dir, sha256


def specification():
    return json.loads((REPO / "config/wine-hotfix.json").read_text())


def previous_specification():
    """One pinned rollback revision; never interpret a receipt ID as a path."""
    return json.loads((REPO / "config/wine-hotfix-previous.json").read_text())


def selected_specification(revision):
    current = specification()
    if revision == current['id']:
        return current
    previous = previous_specification()
    if revision == previous['id']:
        return previous
    raise ManagerError('Unknown Wine hotfix revision. Keep Steam closed and inspect the receipt before changing it.')


def verify(directory, spec=None):
    spec = specification() if spec is None else spec
    directory = no_symlinks(directory)
    for name, digest in spec["files"].items():
        path = no_symlinks(directory / name)
        if not path.is_file() or sha256(path) != digest:
            raise ManagerError(f"Wine hotfix integrity check failed: {name}. Rebuild the pinned hotfix; no unverified DLL will be loaded.")
    return directory


def compatible(profile, spec):
    return (for_profile(profile).hotfixes and profile.get("provider") == "wine" and profile.get("wine_family") == "highball"
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
    spec = selected_specification(state.get('id'))
    if not compatible(profile, spec):
        raise ManagerError("Active Wine hotfix does not match this runtime. Disable it with Steam closed before changing runtimes.")
    return verify(workspace / "Runtimes" / spec["id"], spec)


def status(profile):
    directory = active(profile)
    return {"enabled": directory is not None, "id": directory.name if directory else None,
            "verified": directory is not None}


def configure(workspace, profile, enabled, previous=False):
    from .backup import wine_processes_running
    if wine_processes_running():
        raise ManagerError("Exit Windows Steam and all Wine bottles before changing the hotfix; running processes retain their DLL environment.")
    spec = previous_specification() if previous else specification()
    if previous and not enabled:
        raise ManagerError('Choose either the previous hotfix or disable all hotfixes.')
    if enabled:
        if not compatible(profile, spec):
            raise ManagerError("This hotfix only supports the pinned Highball runtime.")
        if not stage_available(workspace, spec):
            raise ManagerError('The selected hotfix payload is unavailable. Use a preview that bundles it or build the pinned recipe.')
    atomic_json(receipt(workspace, profile), {"schema": 1, "id": spec["id"], "enabled": enabled,
                                            "pin_revision": previous})
    return status(profile)


def stage_available(workspace, spec):
    """Publish only a verified payload, without changing the selected revision."""
    target = no_symlinks(Path(workspace) / 'Runtimes' / spec['id'])
    if target.exists():
        verify(target, spec)
        return True
    bundled = REPO / 'runtime-overlays' / spec['id']
    if not bundled.exists():
        return False
    verify(bundled, spec)
    private_dir(target.parent)
    with tempfile.TemporaryDirectory(prefix='.hotfix-', dir=target.parent) as temp:
        stage = Path(temp) / spec['id']
        shutil.copytree(bundled, stage)
        verify(stage, spec)
        stage.rename(target)
    return True


def install_available(workspace, profile):
    """Fresh setup/explicit setup upgrades use a verified payload; preserve opt-out."""
    spec = specification()
    if not compatible(profile, spec):
        return False
    selected = receipt(workspace, profile)
    existing = None
    if selected.exists():
        state = json.loads(selected.read_text())
        if not state.get('enabled'):
            return False  # An explicit opt-out is never overridden by setup.
        existing = active(profile)  # Validate the old revision before upgrading.
        if state.get('pin_revision') or existing.name == spec['id']:
            return True
    if not stage_available(workspace, spec):
        return existing is not None
    configure(workspace, profile, True)
    return True
