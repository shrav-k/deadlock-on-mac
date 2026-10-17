#!/usr/bin/env python3
"""Build and run small Windows conformance probes; never install Steam or a game.

Use --profile for a registered Wine/DXMT stack, or --wine for a candidate in a
new disposable prefix. Candidate testing never touches an existing Steam bottle.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from deadlock_mac.cli import load_profile
from deadlock_mac.runtime import clean_env, environment, wine_binary
from deadlock_mac.storage import ManagerError, atomic_json, private_dir, sha256
from deadlock_mac import hotfix


def check(workspace, compiler, profile_id=None, candidate=None, graphics=False):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = private_dir(workspace / "Tools/runtime-checks" / run_id)
    compiler = compiler.resolve()
    if profile_id:
        profile = load_profile(workspace, profile_id)
        if profile["provider"] != "wine":
            raise ManagerError("This harness currently tests Wine providers only.")
        wine, env = wine_binary(profile), environment(profile)
        metadata = {"profile": profile_id, "runtime": profile["runtime_version"],
                    "dxmt": profile["dxmt_version"], "hotfix": hotfix.status(profile)}
    else:
        wine = candidate.resolve()
        env = clean_env()
        env.update(WINEPREFIX=str(root / "prefix"), WINEDEBUG="-all,err+all", WINEDLLOVERRIDES="mscoree,mshtml=")
        metadata = {"runtime": "isolated-candidate", "wine_sha256": sha256(wine), "dxmt": None}
    results = []

    def run(label, argv, timeout=90):
        with (root / (label + ".log")).open("xb") as log:
            result = subprocess.run(list(map(str, argv)), env=env, cwd=root,
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        return result.returncode, (root / (label + ".log")).read_text(errors="replace")

    try:
        code, version = run("version", [wine, "--version"])
        if code:
            raise ManagerError("Wine --version failed; see the private test directory.")
        metadata["reported_version"] = version.strip()
        if candidate:
            code, _ = run("initialize", [wine, "wineboot", "-u"], timeout=180)
            if code:
                raise ManagerError("Candidate prefix initialization failed.")
        for arch, cc, flags in (("x86_64", "x86_64-w64-mingw32-clang", ["-fms-extensions"]),
                                ("i386", "i686-w64-mingw32-clang", [])):
            executable = root / ("device-notify-" + arch + ".exe")
            subprocess.run([str(compiler / cc), *flags, "-O2", str(REPO / "tests/native/device_notify_probe.c"),
                            "-luser32", "-o", str(executable)], check=True)
            code, output = run("device-notify-" + arch, [wine, executable])
            expected = ("null: result=0 error=6 exception=00000000",
                        "readable-invalid: result=0 error=6 exception=00000000",
                        "inaccessible: result=0 error=1066 exception=00000000",
                        "valid-registration: unregister=1", "failures=0")
            results.append({"test": "device-notification", "architecture": arch, "exit_code": code,
                            "passed": code == 0 and all(line in output for line in expected),
                            "probe_sha256": sha256(executable)})
        if graphics:
            executable = root / "d3d11-probe.exe"
            subprocess.run([str(compiler / "x86_64-w64-mingw32-clang"), "-O2",
                            str(REPO / "tests/native/d3d11_probe.c"), "-ld3d11", "-ldxgi", "-ldxguid", "-luser32",
                            "-o", str(executable)], check=True)
            code, output = run("d3d11", [wine, executable])
            results.append({"test": "d3d11-present", "architecture": "x86_64", "exit_code": code,
                            "passed": code == 0 and "PASS: 120 frames presented." in output,
                            "probe_sha256": sha256(executable)})
    finally:
        # Only a newly created candidate prefix may be stopped by this harness.
        # Registered profiles can contain live Steam and are never terminated.
        if candidate:
            subprocess.run([str(wine.parent / "wineserver"), "-k"], env=env, cwd=root,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    report = {"schema": 1, "metadata": metadata, "tests": results,
              "passed": all(item["passed"] for item in results),
              "scope": "Native API/rendering smoke probes, not Steam login, full Wine conformance, game performance or multiplayer acceptance."}
    atomic_json(root / "report.json", report)
    print(json.dumps(report, indent=2))
    print(f"Private test artifacts: {root}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--compiler-bin", type=Path, required=True)
    runtime = parser.add_mutually_exclusive_group(required=True)
    runtime.add_argument("--profile")
    runtime.add_argument("--wine", type=Path)
    parser.add_argument("--graphics", action="store_true", help="Also display a 120-frame D3D11 smoke probe")
    args = parser.parse_args()
    sys.exit(check(args.workspace.expanduser().resolve(), args.compiler_bin,
                   args.profile, args.wine, args.graphics))
