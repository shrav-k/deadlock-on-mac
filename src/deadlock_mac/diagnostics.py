"""Read-only package inspection. No credentials or account files are read."""
from pathlib import Path
import json
import platform
import subprocess

from .runtime import clean_env, environment
from .storage import ManagerError


def display_status():
    """Allowlisted desktop/display inventory; no serial numbers or EDID blobs."""
    if platform.system() != "Darwin":
        return {"verified": False, "displays": []}
    try:
        result = subprocess.run(["/usr/sbin/system_profiler", "SPDisplaysDataType", "-json"],
                                capture_output=True, text=True, timeout=20, check=True, env=clean_env())
        displays = []
        for gpu in json.loads(result.stdout).get("SPDisplaysDataType", []):
            for display in gpu.get("spdisplays_ndrvs", []):
                displays.append({"gpu": gpu.get("sppci_model"), "name": display.get("_name"),
                                 "connection": display.get("spdisplays_connection_type"),
                                 "main": display.get("spdisplays_main") == "spdisplays_yes",
                                 "mirrored": display.get("spdisplays_mirror") == "spdisplays_on",
                                 "desktop_mode": display.get("_spdisplays_resolution"),
                                 "physical_pixels": display.get("_spdisplays_pixels")})
        return {"verified": True, "displays": displays,
                "scope": "macOS display inventory, not verification of the game's render resolution or fullscreen coverage"}
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        return {"verified": False, "displays": []}


def power_status():
    """Read only the power source and low-power flags, not battery identifiers."""
    if platform.system() != "Darwin":
        return {"source": "unknown", "low_power_mode": None}
    try:
        battery = subprocess.run(["/usr/bin/pmset", "-g", "batt"], capture_output=True,
                                 text=True, timeout=10, check=True, env=clean_env()).stdout
        source = "AC Power" if "'AC Power'" in battery else "Battery Power" if "'Battery Power'" in battery else "unknown"
        settings = subprocess.run(["/usr/bin/pmset", "-g", "custom"], capture_output=True,
                                  text=True, timeout=10, check=True, env=clean_env()).stdout
        current, low_power = None, None
        for line in settings.splitlines():
            if line.endswith(":"):
                current = line.strip().removesuffix(":")
            elif current == source and line.strip().startswith("lowpowermode "):
                low_power = line.split()[-1] == "1"
        return {"source": source, "low_power_mode": low_power}
    except (OSError, subprocess.SubprocessError):
        return {"source": "unknown", "low_power_mode": None}


def engine_dependencies(profile):
    if platform.system() != "Darwin" or profile["provider"] != "wine":
        raise ManagerError("Dependency inspection currently supports free Wine profiles on macOS.")
    modules = sorted((Path(profile["runtime"]) / "lib/wine/x86_64-unix").glob("*.so"))
    if not modules:
        raise ManagerError("No Wine Unix modules found.")
    result = subprocess.run(["/usr/bin/otool", "-L", *map(str, modules)], capture_output=True,
                            text=True, timeout=30, check=True, env=clean_env())
    env = environment(profile)
    search = [Path(p) for p in env["DYLD_FALLBACK_LIBRARY_PATH"].split(":")]
    missing = []
    current = None
    for line in result.stdout.splitlines():
        if not line.startswith("\t") and line.endswith(":"):
            current = Path(line[:-1])
            continue
        if not line.startswith("\t") or current is None:
            continue
        library = line.strip().split(" (")[0]
        # System libraries can reside solely in Apple's shared dyld cache.
        if library.startswith(("/System/", "/usr/lib/")):
            continue
        if library.startswith("@rpath/"):
            present = any((p / library.removeprefix("@rpath/")).exists() for p in search)
        elif library.startswith("@loader_path/"):
            present = (current.parent / library.removeprefix("@loader_path/")).exists()
        else:
            present = Path(library).exists() or any((p / Path(library).name).exists() for p in search)
        if not present:
            missing.append({"module": current.name, "library": Path(library).name})
    return {"modules_inspected": len(modules), "unresolved": missing,
            "scope": "Direct Mach-O imports of Wine Unix modules; not a recursive dependency or gameplay test."}
