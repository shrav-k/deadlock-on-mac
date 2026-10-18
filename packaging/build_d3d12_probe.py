#!/usr/bin/env python3
"""Build the isolated GPU probe; does not install a renderer or run Wine."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from deadlock_mac.storage import atomic_json, download, sha256, unpack


def build(output, downloads):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    compiler = json.loads((REPO / 'config/wine-hotfix.json').read_text())['inputs']['llvm']
    archive = download(compiler['url'], compiler['sha256'], Path(downloads) / compiler['filename'])
    source = REPO / 'tests/native/d3d12_probe.c'
    with tempfile.TemporaryDirectory(prefix='launcher-d3d12-probe-') as temporary:
        stage = Path(temporary).resolve()
        unpack(archive, stage / 'compiler')
        cc = next((stage / 'compiler').glob('llvm-mingw-*/bin/x86_64-w64-mingw32-clang'))
        executable = stage / 'd3d12-probe.exe'
        subprocess.run([str(cc), '-Wall', '-Wextra', '-Werror', '-O2',
                        '-DWIDL_EXPLICIT_AGGREGATE_RETURNS=1', str(source), '-o', str(executable),
                        '-ld3d12', '-ldxgi', '-ldxguid', '-ld3dcompiler', '-luser32'], check=True)
        shutil.copy2(executable, output / executable.name)
        licenses = output / 'licenses'
        licenses.mkdir(exist_ok=True)
        shutil.copyfile(cc.parent.parent / 'LICENSE.TXT', licenses / 'LLVM.txt')
        shutil.copyfile(cc.parent.parent / 'x86_64-w64-mingw32/share/mingw32/COPYING.MinGW-w64-runtime.txt',
                        licenses / 'MinGW-runtime.txt')
    atomic_json(output / 'receipt.json', {'schema': 1, 'compiler': compiler,
                'source_sha256': sha256(source), 'executable_sha256': sha256(output / 'd3d12-probe.exe'),
                'runtime_executed': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--downloads', type=Path, required=True)
    args = parser.parse_args()
    build(args.output, args.downloads)
