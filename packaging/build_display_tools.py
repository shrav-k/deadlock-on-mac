#!/usr/bin/env python3
"""Compile the owned display helpers; no installed Wine/game files are modified."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from deadlock_mac.storage import download, unpack, sha256, atomic_json


def build(output, downloads):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    sources = {name: sha256(REPO / 'native' / name) for name in ('host_displays.swift', 'wine_displays.c')}
    receipt = output / 'receipt.json'
    if receipt.is_file():
        previous = json.loads(receipt.read_text())
        if (previous.get('sources') == sources and set(previous.get('files', {})) == {'wine-displays.exe', 'host-displays'}
                and (output / 'licenses/LLVM.txt').is_file() and (output / 'licenses/MinGW-runtime.txt').is_file()
                and all((output / name).is_file() and sha256(output / name) == digest
                        for name, digest in previous.get('files', {}).items())):
            return
    compiler = json.loads((REPO / 'config/wine-hotfix.json').read_text())['inputs']['llvm']
    archive = download(compiler['url'], compiler['sha256'], Path(downloads) / compiler['filename'])
    with tempfile.TemporaryDirectory(prefix='deadlock-display-build-') as temporary:
        stage = Path(temporary).resolve()
        unpack(archive, stage / 'compiler')
        cc = next((stage / 'compiler').glob('llvm-mingw-*/bin/x86_64-w64-mingw32-clang'))
        subprocess.run([str(cc), '-Wall', '-Wextra', '-Werror', '-O2', '-municode',
                        str(REPO / 'native/wine_displays.c'), '-o', str(stage / 'wine-displays.exe'),
                        '-ld3d11', '-ldxgi', '-ldxguid', '-luser32'], check=True)
        subprocess.run(['/usr/bin/xcrun', 'swiftc', '-O', '-target', 'arm64-apple-macos15.0',
                        str(REPO / 'native/host_displays.swift'), '-o', str(stage / 'host-displays')], check=True)
        for name in ('wine-displays.exe', 'host-displays'):
            shutil.copy2(stage / name, output / name)
        licenses = output / 'licenses'
        licenses.mkdir(exist_ok=True)
        compiler_root = cc.parent.parent
        shutil.copyfile(compiler_root / 'LICENSE.TXT', licenses / 'LLVM.txt')
        shutil.copyfile(compiler_root / 'x86_64-w64-mingw32/share/mingw32/COPYING.MinGW-w64-runtime.txt', licenses / 'MinGW-runtime.txt')
        atomic_json(receipt, {'schema': 1, 'sources': sources, 'compiler': compiler,
                              'files': {name: sha256(output / name) for name in ('wine-displays.exe', 'host-displays')}})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=REPO / 'native-bin')
    parser.add_argument('--downloads', type=Path, required=True)
    args = parser.parse_args()
    build(args.output, args.downloads)
