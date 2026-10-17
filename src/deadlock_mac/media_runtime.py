"""Pinned media libraries for the Highball ABI, isolated from system/Homebrew libs."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from .catalog import REPO, runtime_set
from .storage import ManagerError, no_symlinks, private_dir, sha256, unpack


def specification():
    return json.loads((REPO / 'config/media-runtime.json').read_text())


def verify(directory, spec=None):
    spec = specification() if spec is None else spec
    directory = no_symlinks(directory)
    if not spec['files'] or set(spec['files']) != {f'lib/{name}' for name in spec['libraries']}:
        raise ManagerError('Media runtime has no complete reviewed library hashes.')
    for name, digest in spec['files'].items():
        path = no_symlinks(directory / name)
        if not path.is_file() or sha256(path) != digest:
            raise ManagerError(f'Media runtime integrity check failed: {name}. Run runtime-install or reinstall the app.')
    source = spec['inputs']['ffmpeg']
    archive = no_symlinks(directory / source['filename'])
    if not archive.is_file() or sha256(archive) != source['sha256']:
        raise ManagerError('Media corresponding-source archive is missing or changed.')
    for name in ('COPYING.LGPLv2.1', 'provenance.json', 'build_media_runtime.py', 'config.h'):
        if not no_symlinks(directory / name).is_file():
            raise ManagerError(f'Media package provenance/license is missing: {name}')
    expected = {*spec['files'], source['filename'], 'COPYING.LGPLv2.1',
                'provenance.json', 'build_media_runtime.py', 'config.h'}
    actual = {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() or p.is_symlink()}
    if actual != expected:
        raise ManagerError('Media runtime contains unexpected files; preserve it for inspection.')
    return directory


def verified_archive(archive, destination):
    spec = specification()
    unpack(no_symlinks(archive), destination)
    if {p.name for p in destination.iterdir()} != {spec['id']}:
        raise ManagerError('Unexpected media package layout.')
    return verify(destination / spec['id'], spec)


def package(downloads):
    """App ships a sealed payload. Source developers can build it with Apple's CLT."""
    spec = specification()
    bundled = REPO / 'runtime-payloads' / (spec['id'] + '.tar.xz')
    cached = Path(downloads) / bundled.name
    if bundled.is_file():
        return no_symlinks(bundled)
    if cached.is_file():
        return no_symlinks(cached)
    builder = REPO / 'packaging/build_media_runtime.py'
    if not builder.is_file():
        raise ManagerError('This app is missing its media package. Reinstall a complete manager build.')
    print('Building pinned media libraries with Apple Command Line Tools (source checkout only)…', flush=True)
    subprocess.run([sys.executable, str(builder), '--output', str(cached),
                    '--downloads', str(downloads)], check=True)
    return cached


def install(workspace, family='highball'):
    spec = specification()
    if runtime_set(family)['wine'] != spec['runtime_version']:
        return None
    destination = no_symlinks(Path(workspace) / 'Runtimes' / spec['id'])
    if destination.exists():
        return verify(destination, spec)
    archive = package(Path(workspace) / 'Downloads')
    private_dir(destination.parent)
    with tempfile.TemporaryDirectory(prefix='.media-install-', dir=destination.parent) as temporary:
        staged = verified_archive(archive, Path(temporary) / 'extracted')
        staged.rename(destination)
    return destination


def library_directory(profile):
    if profile.get('runtime_version') != specification()['runtime_version'] or profile.get('provider') != 'wine':
        return None
    directory = Path(profile['prefix']).parents[1] / 'Runtimes' / specification()['id']
    if not directory.exists():
        raise ManagerError('Matching FFmpeg libraries are missing. Close Windows Steam and run Set Up Steam or runtime-install.')
    return verify(directory) / 'lib'
