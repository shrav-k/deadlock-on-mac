"""Read-only package inspection. No credentials or account files are read."""
from pathlib import Path
import platform
import subprocess

from .runtime import clean_env, environment
from .storage import ManagerError


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
