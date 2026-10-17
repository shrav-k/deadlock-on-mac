#!/usr/bin/env python3
"""Build private x86_64 LGPL FFmpeg libraries; no Homebrew or global installs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from deadlock_mac.storage import download, unpack, sha256, atomic_json, no_symlinks


def configure_arguments(prefix, nasm):
    return [f'--prefix={prefix}', '--arch=x86_64', '--target-os=darwin', '--enable-cross-compile',
            '--cc=/usr/bin/clang -arch x86_64', '--extra-cflags=-mmacosx-version-min=15.0',
            '--extra-ldflags=-mmacosx-version-min=15.0', f'--x86asmexe={nasm}',
            '--install-name-dir=@rpath', '--enable-shared', '--disable-static',
            '--disable-programs', '--disable-doc', '--disable-debug', '--disable-autodetect',
            '--disable-network', '--disable-avdevice', '--disable-avfilter', '--disable-swscale',
            '--disable-encoders', '--disable-muxers', '--enable-zlib']


def build(output, downloads, *, review=False):
    spec = json.loads((REPO / 'config/media-runtime.json').read_text())
    output = no_symlinks(output)
    if output.exists():
        raise SystemExit('Use a new media build output; existing outputs are preserved.')
    output.parent.mkdir(parents=True, exist_ok=True)
    inputs = {}
    for key, item in spec['inputs'].items():
        inputs[key] = download(item['url'], item['sha256'], Path(downloads) / item['filename'])
    with tempfile.TemporaryDirectory(prefix='.media-build-', dir=output.parent) as temporary:
        root = Path(temporary)
        env = {key: os.environ[key] for key in ('HOME', 'TMPDIR', 'DEVELOPER_DIR') if key in os.environ}
        env.update(PATH='/usr/bin:/bin:/usr/sbin:/sbin', LC_ALL='C', SOURCE_DATE_EPOCH='1790985600')
        log = root / 'build.log'
        def run(args, cwd):
            with log.open('ab') as stream:
                subprocess.run(list(map(str, args)), cwd=cwd, env=env, stdout=stream,
                               stderr=subprocess.STDOUT, check=True, timeout=900)
        try:
            for key, archive in inputs.items():
                unpack(archive, root / key)
            nasm = root / 'nasm' / spec['inputs']['nasm']['root']
            run(['./configure', '--disable-doc'], nasm)
            run(['/usr/bin/make', '-j8', 'nasm'], nasm)
            source = root / 'ffmpeg' / spec['inputs']['ffmpeg']['root']
            # Highball's Mach-O module binds codec/util symbols to libavformat.
            # Re-export those same-ABI libraries; never rename an older ABI or
            # patch the immutable Wine engine's symbol bindings.
            makefile = source / 'ffbuild/library.mak'
            original = makefile.read_text()
            needle = '$(NAME)LINK_EXTRA = $(FFEXTRALIBS)'
            if original.count(needle) != 1:
                raise SystemExit('Pinned FFmpeg linker recipe changed; review before building.')
            # Apple's linker uses the first occurrence of a library. These
            # options must precede the ordinary -lavcodec/-lavutil dependencies.
            makefile.write_text('DM_REEXPORT_avformat = -Wl,-reexport_library,libavcodec/libavcodec.63.dylib -Wl,-reexport_library,libavutil/libavutil.61.dylib\n' +
                                original.replace(needle, '$(NAME)LINK_EXTRA = $(DM_REEXPORT_$(NAME)) $(FFEXTRALIBS)'))
            builddir = root / 'objects'; builddir.mkdir()
            prefix = root / 'install/opt/deadlock-media'
            env['PATH'] = str(nasm) + ':' + env['PATH']
            flags = configure_arguments('/opt/deadlock-media', 'nasm')
            run([source / 'configure', *flags], builddir)
            run(['/usr/bin/make', '-j8'], builddir)
            run(['/usr/bin/make', 'install-libs', f'DESTDIR={root / "install"}'], builddir)
            payload = root / spec['id']; (payload / 'lib').mkdir(parents=True)
            for name in spec['libraries']:
                shutil.copyfile(prefix / 'lib' / name, payload / 'lib' / name)
            commands = subprocess.check_output(['/usr/bin/otool', '-l', str(payload / 'lib/libavformat.63.dylib')], text=True)
            for name in ('libavcodec.63.dylib', 'libavutil.61.dylib'):
                if not any('LC_REEXPORT_DYLIB' in entry and f'@rpath/{name} ' in entry
                           for entry in commands.split('Load command ')):
                    raise SystemExit(f'Missing Highball symbol re-export: {name}')
            shutil.copyfile(source / 'COPYING.LGPLv2.1', payload / 'COPYING.LGPLv2.1')
            # Corresponding source travels with the local binary package.
            shutil.copyfile(inputs['ffmpeg'], payload / spec['inputs']['ffmpeg']['filename'])
            shutil.copyfile(__file__, payload / 'build_media_runtime.py')
            shutil.copyfile(builddir / 'config.h', payload / 'config.h')
            libraries = {f'lib/{name}': sha256(payload / 'lib' / name) for name in spec['libraries']}
            if not review and libraries != spec['files']:
                raise SystemExit('Media output differs from reviewed hashes; inspect the build before changing pins.')
            atomic_json(payload / 'provenance.json', {
                'schema': 1, 'id': spec['id'], 'inputs': spec['inputs'], 'libraries': libraries,
                'configure': flags, 'compiler': subprocess.check_output(['/usr/bin/clang', '--version'], env=env, text=True),
                'license': 'LGPL-2.1-or-later; GPL/nonfree and external codec libraries disabled',
            })
            # A tar payload avoids app signing changing reviewed library bytes.
            with tarfile.open(root / 'payload.tar.xz', 'w:xz') as archive:
                archive.add(payload, arcname=spec['id'])
            (root / 'payload.tar.xz').rename(output)
            print(json.dumps({'archive': str(output), 'sha256': sha256(output), 'files': libraries}, indent=2))
        finally:
            if log.exists(): shutil.copyfile(log, output.with_suffix('.build.log'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--downloads', type=Path, required=True)
    parser.add_argument('--review', action='store_true', help='Produce a candidate for review; never installs or updates pins')
    args = parser.parse_args()
    build(args.output, args.downloads, review=args.review)
