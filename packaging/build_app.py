#!/usr/bin/env python3
"""Build an ad-hoc signed local preview. Publishing requires Developer ID/notarization."""
import argparse
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from deadlock_mac.storage import download, private_dir, unpack, sha256
from deadlock_mac import __version__
from deadlock_mac import hotfix


def build(output, downloads, wine_hotfix=None):
    """Publish a complete, verified build; failed staging never replaces an app."""
    output = Path(output).expanduser().absolute()
    if output.exists() or output.is_symlink() or output.suffix != ".app":
        raise SystemExit("Choose a new output path ending in .app; existing builds are preserved.")
    private_dir(output.parent)
    with tempfile.TemporaryDirectory(prefix=".deadlock-build-", dir=output.parent) as temporary:
        staged = Path(temporary) / output.name
        build_staged(staged, downloads, wine_hotfix)
        if output.exists() or output.is_symlink():
            raise SystemExit("Output appeared during the build; it was left unchanged.")
        staged.rename(output)
        staged.with_suffix(".sha256.json").replace(output.with_suffix(".sha256.json"))
    print(output)
    print("Local preview built. No public release or notarization was performed.")


def build_staged(output, downloads, wine_hotfix=None):
    lock = json.loads((REPO / "packaging/python-lock.json").read_text())
    archive = download(lock["url"], lock["sha256"], Path(downloads) / lock["filename"])
    resources = private_dir(output / "Contents/Resources")
    macos = private_dir(output / "Contents/MacOS")
    stage = resources / "python-extraction"
    unpack(archive, stage)
    (stage / "python").rename(resources / "python")
    stage.rmdir()
    manager = resources / "manager"
    manager.mkdir()
    subprocess.run([sys.executable, str(REPO / "packaging/build_display_tools.py"),
                    "--downloads", str(downloads)], check=True)
    for name in ("src", "bin", "config", "docs", "native", "native-bin"):
        shutil.copytree(REPO / name, manager / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
    for name in ("LICENSE", "README.md", "SECURITY.md", "CHANGELOG.md"):
        shutil.copyfile(REPO / name, manager / name)
    if wine_hotfix is not None:
        spec = hotfix.specification()
        source = hotfix.verify(wine_hotfix, spec)
        if not (source / "COPYING.LIB").is_file() or not (source / "provenance.json").is_file():
            raise SystemExit("Hotfix license and source provenance are required for bundling.")
        destination = manager / "runtime-overlays" / spec["id"]
        for name in (*spec["files"], "COPYING.LIB", "provenance.json"):
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, path)
    shutil.copyfile(REPO / "packaging/launcher.py", resources / "launcher.py")
    certificate = resources / "python/lib/python3.13/site-packages/pip/_vendor/certifi/cacert.pem"
    if not certificate.is_file():
        raise SystemExit("Pinned Python distribution did not provide its expected certifi trust store.")
    info = {"CFBundleIdentifier": "dev.shrav-k.deadlock-manager", "CFBundleName": "Deadlock Manager",
            "CFBundleDisplayName": "Deadlock Manager", "CFBundleExecutable": "DeadlockManager",
            "CFBundlePackageType": "APPL", "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__, "LSMinimumSystemVersion": "15.0", "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.utilities",
            "NSMicrophoneUsageDescription": "Deadlock can use your microphone for in-game voice chat when you enable it."}
    with (output / "Contents/Info.plist").open("wb") as stream:
        plistlib.dump(info, stream)
    subprocess.run(["/usr/bin/xcrun", "swiftc", "-parse-as-library", "-O", "-target", "arm64-apple-macos15.0",
                    str(REPO / "packaging/ManagerLifecycle.swift"), str(REPO / "packaging/WineActivation.swift"),
                    str(REPO / "packaging/DeadlockManager.swift"),
                    "-o", str(macos / "DeadlockManager")], check=True)
    # Exercise the same isolated entry point the UI will run before signing it.
    subprocess.run([str(resources / "python/bin/python3"), "-I", "-B", str(resources / "launcher.py"), "--help"],
                   check=True, stdout=subprocess.DEVNULL, timeout=30)
    version = subprocess.check_output([str(resources / "python/bin/python3"), "-I", "-B",
                                      str(resources / "launcher.py"), "--version"], text=True, timeout=30).strip()
    if version != __version__:
        raise SystemExit("Bundled manager version differs from the app bundle version.")
    inputs = {"manager_version": __version__, "python": lock, "certificates_sha256": sha256(certificate),
              "wine_hotfix": hotfix.specification() if wine_hotfix is not None else None,
              "swift": subprocess.check_output(["/usr/bin/xcrun", "swiftc", "--version"], text=True).strip(),
              "source_files": {str(p.relative_to(REPO)): sha256(p)
                               for p in sorted([p for d in ("src", "bin", "config", "docs", "packaging", "native")
                                                for p in (REPO / d).rglob("*")]
                                               + [REPO / name for name in ("LICENSE", "README.md", "SECURITY.md", "CHANGELOG.md")])
                               if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"},
              "distribution_status": "local development preview; ad-hoc signed, not notarized",
              "license_scope": "Python/Pip bundled license files retained; full dependency SBOM and license audit remain release gates"}
    (resources / "build-inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    # Sign only this newly built application, never a downloaded game runtime or vendor app.
    subprocess.run(["/usr/bin/codesign", "--force", "--deep", "--sign", "-", str(output)], check=True)
    # Deep signing may replace the host helper's ad-hoc signature. Seal its
    # final bytes in the helper receipt, then reseal only the enclosing bundle.
    helper_receipt = manager / "native-bin/receipt.json"
    helpers = json.loads(helper_receipt.read_text())
    helpers["files"] = {name: sha256(manager / "native-bin" / name) for name in helpers["files"]}
    helper_receipt.write_text(json.dumps(helpers, indent=2) + "\n")
    subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(output)], check=True)
    subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(output)], check=True)
    manifest = {str(p.relative_to(output)): sha256(p) for p in sorted(output.rglob("*"))
                if p.is_file() and not p.is_symlink()}
    output.with_suffix(".sha256.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--wine-hotfix", type=Path, help="Reviewed local DLL overlay to include in fresh setups")
    args = parser.parse_args()
    build(args.output, args.downloads, args.wine_hotfix)
