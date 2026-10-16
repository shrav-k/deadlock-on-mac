#!/usr/bin/env python3
"""Owned-file decoding and isolated Wine bridge probes. Never starts Steam/game."""
import argparse
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import wave

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from deadlock_mac import media_runtime
from deadlock_mac.cli import load_profile
from deadlock_mac.runtime import environment, wine_binary, clean_env
from deadlock_mac.storage import download, unpack, atomic_json


def check(workspace, profile_id, report):
    profile = load_profile(workspace, profile_id)
    media = media_runtime.library_directory(profile)
    if media is None: raise SystemExit('This probe requires the managed FFmpeg runtime.')
    spec = media_runtime.specification()
    results = []
    report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.media-probes-', dir=report.parent) as temporary:
        root = Path(temporary).resolve()
        unpack(media.parent / spec['inputs']['ffmpeg']['filename'], root / 'source')
        source = root / 'source' / spec['inputs']['ffmpeg']['root']
        (source / 'libavutil/avconfig.h').write_text('#define AV_HAVE_BIGENDIAN 0\n#define AV_HAVE_FAST_UNALIGNED 1\n')
        with wave.open(str(root / 'tone.wav'), 'wb') as audio:
            audio.setparams((1, 2, 48000, 48000, 'NONE', 'not compressed'))
            audio.writeframes(b''.join(struct.pack('<h', int(4000*math.sin(2*math.pi*440*i/48000))) for i in range(48000)))
        executable = root / 'decode'
        subprocess.run(['/usr/bin/xcrun', 'clang', '-arch', 'x86_64', '-I', str(source),
                        str(REPO / 'tests/native/media_decode.c'),
                        *[str(media / name) for name in spec['libraries']],
                        '-Wl,-rpath,' + str(media), '-o', str(executable)], check=True)
        env = clean_env()
        env['DYLD_FALLBACK_LIBRARY_PATH'] = str(media) + ':/usr/lib'
        result = subprocess.run([str(executable), str(root / 'tone.wav')], env=env, capture_output=True, text=True, timeout=30)
        results.append({'probe': 'native-x86_64-decode', 'exit_code': result.returncode,
                        'stdout': result.stdout, 'stderr': result.stderr})
        if result.returncode: raise RuntimeError(result.stderr or result.stdout)
        compiler = json.loads((REPO / 'config/wine-hotfix.json').read_text())['inputs']['llvm']
        archive = download(compiler['url'], compiler['sha256'], workspace / 'Downloads' / compiler['filename'])
        unpack(archive, root / 'compiler')
        compiler_bin = next((root / 'compiler').glob('llvm-mingw-*/bin'))
        env = environment(profile)
        env.update(WINEPREFIX=str(root / 'prefix'), WINEDEBUG='-all,err+all,+dmo,warn+module', WINEDLLOVERRIDES='mscoree,mshtml=')
        wine = wine_binary(profile)
        try:
            for arch, cc in (('x86_64', 'x86_64-w64-mingw32-clang'), ('i386', 'i686-w64-mingw32-clang')):
                probe = root / f'probe-{arch}.exe'
                subprocess.run([str(compiler_bin / cc), '-O2', str(REPO / 'tests/native/wine_media.c'), '-o', str(probe)], check=True)
                result = subprocess.run([str(wine), str(probe)], env=env, cwd=root,
                                        capture_output=True, text=True, timeout=180)
                (report.parent / f'media-{arch}.log').write_text(result.stdout + result.stderr)
                passed = result.returncode == 0 and 'PASS Wine media bridge' in result.stdout and 'Failed to init unixlib' not in result.stderr
                results.append({'probe': f'wine-media-{arch}', 'exit_code': result.returncode, 'passed': passed})
                atomic_json(report, {'schema': 1, 'phase': 'testing', 'results': results})
        finally:
            # Only this harness-created prefix is stopped. No registered bottle is modified.
            subprocess.run([str(wine.parent / 'wineserver'), '-k'], env=env, cwd=root, timeout=15)
            subprocess.run([str(wine.parent / 'wineserver'), '-w'], env=env, cwd=root, timeout=30)
    passed = all(r['exit_code'] == 0 and r.get('passed', True) for r in results)
    atomic_json(report, {'schema': 1, 'passed': passed, 'scope': 'Owned media decode and disposable Wine prefix; no Steam or gameplay', 'results': results})
    print(json.dumps(results, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--profile', default='highball')
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    sys.exit(check(a.workspace.resolve(), a.profile, a.report.resolve()))
