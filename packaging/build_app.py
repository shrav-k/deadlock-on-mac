#!/usr/bin/env python3
"""Build an ad-hoc signed local preview. Publishing requires Developer ID/notarization."""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from deadlock_mac.storage import download, private_dir, unpack, sha256, no_symlinks, lock, atomic_json
from deadlock_mac import __version__
from deadlock_mac import hotfix
from deadlock_mac import media_runtime


def verified_preview(app):
    """Only rotate this project's complete, unchanged build outputs."""
    no_symlinks(app)
    manifest = no_symlinks(app.with_suffix('.sha256.json'))
    if not app.is_dir() or not manifest.is_file():
        raise SystemExit(f'Preview or its hash manifest is missing: {app}')
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    if info.get('CFBundleIdentifier') != 'dev.shrav-k.deadlock-manager':
        raise SystemExit(f'Refusing to replace an unrelated application: {app}')
    hashes = json.loads(manifest.read_text())
    actual = {str(p.relative_to(app)): sha256(p) for p in app.rglob('*')
              if p.is_file() and not p.is_symlink()}
    if not hashes or hashes != actual:
        raise SystemExit(f'Preview has changed since verification; preserve it for inspection: {app}')
    return {'schema': 1, 'kind': 'deadlock-manager-preview',
            'version': info['CFBundleShortVersionString'], 'manifest_sha256': sha256(manifest),
            'files': hashes, 'build_inputs': json.loads((app / 'Contents/Resources/build-inputs.json').read_text())}


def require_closed(apps):
    # Includes the bundled Python Play watcher, which outlives the GUI. Do not
    # remove an interpreter/resources while a game session still depends on it.
    result = subprocess.run(['/bin/ps', '-ww', '-axo', 'comm='], capture_output=True,
                            text=True, check=True, timeout=10)
    for app in apps:
        if any(line.strip().startswith(str(app.resolve()) + '/') for line in result.stdout.splitlines()):
            raise SystemExit(f'Close this manager and finish its game/diagnostic session before replacing it: {app}')


def replacement_inputs(output):
    previous = output.parent / 'Previous' / output.name
    transaction = output.parent / '.preview-transaction'
    if transaction.exists() or transaction.is_symlink():
        raise SystemExit(f'An interrupted preview replacement needs inspection before another build: {transaction}')
    apps = []
    for app in (output, previous):
        no_symlinks(app)
        manifest = app.with_suffix('.sha256.json')
        if app.exists() or manifest.exists() or manifest.is_symlink():
            verified_preview(app)
            apps.append(app)
    require_closed(apps)
    if previous.exists() and not output.exists():
        raise SystemExit('The current preview is missing. Restore Previous before replacing it.')
    return previous, apps


def prune_history(history, protected):
    """Bound only this publisher's own receipts; leave other history untouched."""
    receipts = []
    for path in history.glob('*.json'):
        if path.is_symlink():
            continue
        try:
            data = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if (isinstance(data, dict) and data.get('schema') == 1 and data.get('kind') == 'deadlock-manager-preview'
                and data.get('manifest_sha256') == path.stem):
            receipts.append(path)
    keep = {history / (digest + '.json') for digest in protected}
    for path in sorted(receipts, key=lambda p: p.stat().st_mtime, reverse=True):
        if len(keep) < 20:
            keep.add(path)
        if path not in keep:
            path.unlink()


def publish_replacement(staged, output):
    previous, apps = replacement_inputs(output)  # Recheck after compilation.
    verified_preview(staged)
    history = private_dir(output.parent / 'build-history')
    protected = []
    for app in (*apps, staged):
        receipt = verified_preview(app)
        atomic_json(history / (receipt['manifest_sha256'] + '.json'), receipt)
        if app != previous:
            protected.append(receipt['manifest_sha256'])
    transaction = output.parent / '.preview-transaction'
    transaction.mkdir(mode=0o700)
    # This journal survives an unexpected process/power interruption. Never
    # auto-delete it on recovery failure, and never guess which app is current.
    atomic_json(transaction / 'journal.json', {'output': str(output), 'previous': str(previous),
                                             'staged': str(staged), 'phase': 'publishing'})
    private_dir(previous.parent)
    undo = []
    def move(source, destination):
        source.rename(destination)
        undo.append((destination, source))
    try:
        if previous.exists():
            move(previous, transaction / 'previous.app')
            move(previous.with_suffix('.sha256.json'), transaction / 'previous.sha256.json')
        if output.exists():
            move(output, previous)
            move(output.with_suffix('.sha256.json'), previous.with_suffix('.sha256.json'))
        move(staged, output)
        move(staged.with_suffix('.sha256.json'), output.with_suffix('.sha256.json'))
    except BaseException:
        try:
            for source, destination in reversed(undo):
                source.rename(destination)
        except BaseException as recovery:
            raise SystemExit(f'Preview rollback needs manual recovery; retained files are in {transaction}: {recovery}')
        shutil.rmtree(transaction)
        raise
    # The new preview is complete and the previous current app is the rollback.
    # Remove only the verified older rollback owned by this transaction.
    shutil.rmtree(transaction)
    prune_history(history, protected)


def build(output, downloads, wine_hotfix=None, replace=False):
    """Publish a complete, verified build; failed staging never replaces an app."""
    output = Path(output).expanduser().absolute()
    if output.suffix != '.app' or output.is_symlink() or (output.exists() and not replace):
        raise SystemExit('Use an output path ending in .app. To update a verified preview, close it and use --replace.')
    no_symlinks(output)
    output = output.resolve()
    private_dir(output.parent)
    with lock(output.parent) if replace else nullcontext():
        if replace:
            replacement_inputs(output)
        with tempfile.TemporaryDirectory(prefix=".deadlock-build-", dir=output.parent) as temporary:
            staged = Path(temporary) / output.name
            build_staged(staged, downloads, wine_hotfix)
            if replace:
                publish_replacement(staged, output)
            else:
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
    media_archive = media_runtime.package(downloads)
    with tempfile.TemporaryDirectory(prefix='verify-media-') as temporary:
        media_runtime.verified_archive(media_archive, Path(temporary).resolve() / 'payload')
    payloads = private_dir(manager / 'runtime-payloads')
    shutil.copyfile(media_archive, payloads / (media_runtime.specification()['id'] + '.tar.xz'))
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
        # The previous exit-only revision is a verified subset of this payload.
        # Include it so a fresh installation can roll back without a compiler.
        previous = hotfix.previous_specification()
        if (previous['id'] != spec['id'] and previous['runtime_version'] == spec['runtime_version']
                and all(spec['files'].get(name) == digest for name, digest in previous['files'].items())):
            hotfix.verify(source, previous)
            rollback = manager / 'runtime-overlays' / previous['id']
            for name in (*previous['files'], 'COPYING.LIB'):
                path = rollback / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, path)
            (rollback / 'provenance.json').write_text(json.dumps(
                {**previous, 'bundled_from_verified_subset_of': spec['id']}, indent=2) + '\n')
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
              "media_runtime": media_runtime.specification(),
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
    parser.add_argument("--replace", action="store_true", help="Update a verified closed preview; keep exactly one previous build")
    args = parser.parse_args()
    build(args.output, args.downloads, args.wine_hotfix, replace=args.replace)
