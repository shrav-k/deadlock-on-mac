#!/usr/bin/env python3
"""Build only the matching Wine sechost DLLs from pinned sources and patches.

Does not activate the result, modify a bottle, or replace the original engine.
Requires macOS Command Line Tools; build directories are deliberately append-only.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from deadlock_mac.hotfix import specification, verify
from deadlock_mac.storage import ManagerError, download, private_dir, sha256, unpack, atomic_json


def build(workspace, directory):
    spec = specification()
    output = workspace / "Runtimes" / spec["id"]
    if directory.exists() or output.exists():
        raise ManagerError("Use a new build directory and preserve/move any existing hotfix output first.")
    private_dir(directory)
    archives = {key: download(item["url"], item["sha256"], workspace / "Downloads" / item["filename"])
                for key, item in spec["inputs"].items()}
    unpack(archives["wine"], directory / "source-tree", include="sources/wine")
    unpack(archives["highball"], directory / "recipe")
    unpack(archives["llvm"], directory / "compiler")
    unpack(archives["bison"], directory / "bison-source")
    source = directory / "source-tree/sources/wine"
    patches = next((directory / "recipe").glob("highball-engine-*/patches"))
    compiler = next((directory / "compiler").glob("llvm-mingw-*/bin"))
    bison = directory / "bison-source/bison-3.8.2"
    prefix = directory / "build-tools"
    build_dir = private_dir(directory / "build")
    env = {key: os.environ[key] for key in ("HOME", "TMPDIR", "USER") if key in os.environ}
    env.update(PATH=f"{prefix}/bin:/usr/bin:/bin:/usr/sbin:/sbin:{compiler}",
               DEVELOPER_DIR=os.environ.get("DEVELOPER_DIR", "/Library/Developer/CommandLineTools"),
               SOURCE_DATE_EPOCH=str(spec["source_date_epoch"]), CC="/usr/bin/clang", CXX="/usr/bin/clang++")
    commands = []
    with (directory / "build.log").open("xb") as log:
        def run(argv, cwd=build_dir):
            argv = list(map(str, argv))
            commands.append({"argv": argv, "cwd": str(cwd)})
            atomic_json(directory / "commands.json", commands)
            subprocess.run(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)

        # Include ALL Highball patches, especially its GS-slot Get/SetLastError ABI.
        for folder, items, include in ((patches, spec["highball_patches"], []),
                                      (REPO / "patches/wine", spec["backports"], ["--include=dlls/sechost/service.c"])):
            for name, digest in items.items():
                patch = folder / name
                if sha256(patch) != digest:
                    raise ManagerError(f"Patch digest mismatch: {name}")
                run(["/usr/bin/git", "apply", "--check", *include, patch], source)
                run(["/usr/bin/git", "apply", *include, patch], source)
        run([bison / "configure", f"--prefix={prefix}"], bison)
        run(["/usr/bin/make", "-j6"], bison)
        run(["/usr/bin/make", "install"], bison)
        args = [source / "configure", "--enable-archs=x86_64,i386", "--disable-tests"]
        args += ["--without-" + name for name in ("x", "freetype", "gnutls", "gstreamer", "usb", "alsa",
                                               "cups", "dbus", "fontconfig", "sdl", "opengl")]
        args += ["CC=/usr/bin/clang", "CXX=/usr/bin/clang++",
                 f"CROSSCC={compiler}/x86_64-w64-mingw32-clang",
                 f"x86_64_CC={compiler}/x86_64-w64-mingw32-clang",
                 f"i386_CC={compiler}/i686-w64-mingw32-clang"]
        run(args)
        flags = f"-O2 -ffile-prefix-map={source}=wine -ffile-prefix-map={build_dir}=build"
        # PE build IDs otherwise incorporate debug paths removed by strip below.
        run(["/usr/bin/make", "-j6", f"x86_64_CFLAGS={flags}", f"i386_CFLAGS={flags}",
             "x86_64_LDFLAGS=--no-default-config -fms-hotpatch -Wl,--build-id=none",
             "i386_LDFLAGS=--no-default-config -fms-hotpatch -Wl,--disable-stdcall-fixup -Wl,--build-id=none",
             "dlls/sechost/all"])
        stage = private_dir(directory / "output")
        for name in spec["files"]:
            built = build_dir / "dlls/sechost" / name
            target = private_dir((stage / name).parent) / "sechost.dll"
            shutil.copyfile(built, target)
            run([compiler / "llvm-strip", "--strip-debug", target])
            if b"/Users/" in target.read_bytes():
                raise ManagerError("Local source paths remain in the DLL; output not promoted.")
            original = workspace / "Runtimes" / spec["runtime_version"] / "engine/lib/wine" / name
            def exports(path):
                text = subprocess.check_output([str(compiler / "llvm-readobj"), "--coff-exports", str(path)], text=True)
                return re.findall(r"Ordinal: (\d+)\s+Name: (.*)", text)
            if not original.is_file() or not exports(target) or exports(target) != exports(original):
                raise ManagerError("DLL export ABI differs from the installed pinned engine.")
        # Bytes must match reviewed output, not merely this build's own receipt.
        verify(stage, spec)
        shutil.copyfile(source / "COPYING.LIB", stage / "COPYING.LIB")
        atomic_json(stage / "provenance.json", spec)
        stage.rename(output)
    print(f"Built and verified: {output}. Not activated; run both native probes before live testing.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    args = parser.parse_args()
    build(args.workspace.expanduser().resolve(), args.build_dir.expanduser().resolve())
