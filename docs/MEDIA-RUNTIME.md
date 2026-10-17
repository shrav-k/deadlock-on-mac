# Matching Wine's FFmpeg dependencies

The pinned Highball engine's `winedmo.so` imports FFmpeg ABI 63/63/61. The existing
GStreamer support package contains ABI 61/61/59 and cannot satisfy those imports.
These libraries must coexist: do not rename older dylibs or alter the support
package's copies. A clear file-presence scan alone does not prove the module loads.

The manager supplies a private x86_64 FFmpeg 9.0.2 package, built from the pinned
upstream source with pinned NASM and Apple's compiler. It contains `avformat`,
`avcodec`, `avutil` and `swresample`, dynamically linked under `@rpath`, with no
Homebrew runtime paths or third-party codec dependencies. Network, encoding,
device capture, GPL and nonfree components are not enabled. It uses the LGPL
configuration; the package includes the corresponding FFmpeg source archive,
license, configure output, recipe and provenance.

Highball's two-level Mach-O bindings also expect some codec/util symbols to be
available through `libavformat`. The build recipe re-exports the matching codec
and util libraries from avformat. This is a linker change in our source build,
not a modification to the downloaded Wine engine or a substitution of ABI majors.
The recipe checks the exact pinned Makefile pattern before changing it.
The re-export flags precede ordinary library arguments because Apple's linker
otherwise keeps the first non-re-export reference. A build-time Mach-O check
rejects outputs without both re-export commands.

## Installation and packaging

The current app builder includes a sealed media archive automatically. Setup
verifies its four reviewed dylib hashes and corresponding-source hash, then
extracts it atomically into `Runtimes/ffmpeg-9.0.2-highball-v1`. Failed verification
does not publish an installation; existing installations are verified, not
overwritten. Only the matching Highball profile gains this private library search
directory. Other runtime providers are unaffected.

An existing installation can add it with Windows Steam closed:

```sh
python3 bin/deadlock-mac runtime-install --runtime highball
python3 bin/deadlock-mac runtime-verify --runtime highball
python3 bin/deadlock-mac runtime-dependencies
```

Players using the packaged app need no compiler, NASM, Homebrew or separate FFmpeg
installation. Source-checkout setup builds the package if the local cache is
absent; that development path requires Apple's Command Line Tools. Compiler/build
trees are temporary and removed after completion, with a build log retained.

```sh
DEVELOPER_DIR=/Library/Developer/CommandLineTools python3 packaging/build_media_runtime.py \
  --output ../Downloads/ffmpeg-9.0.2-highball-v1.tar.xz --downloads ../Downloads
```

The output must match reviewed hashes. `--review` creates a candidate without
installing it or changing pins, for a maintainer to inspect after a toolchain
change. Do not automatically accept new output hashes. Exact reproduction across
Apple SDK/compiler versions has not been established. Public binary hosting and
signing belong to the future release workflow; the current local app carries its
own verified payload.

## Verification without gameplay

```sh
DEVELOPER_DIR=/Library/Developer/CommandLineTools python3 packaging/check_media.py \
  --workspace .. --profile highball \
  --report ../DeadlockData/research/media-check/report.json
```

The probe decodes an owned one-second WAV under Rosetta and checks the sample
count and runtime ABI versions. It then exercises Wine's PE→Unix→FFmpeg bridge
for six media types in both 64-bit and 32-bit Windows programs, including an
unsupported-type result. It creates a disposable Wine prefix, never starts Steam
or a game, saves logs and removes the prefix/compiler/source trees afterward.
This tests the actual symbol-binding path that the dependency listing missed.
It is not an in-game cinematic, audio-output or gameplay-performance test.

Unit tests cover first install, idempotence, tampering, wrong ABI filenames,
missing corresponding source, symlinks, unexpected files, isolation from other
runtimes and use of the app payload without compilation. The broader transitive
dependency/plugin audit remains separate from these focused media checks.

On the M2 Max/macOS 26.6.2 development host, the October 16 candidate passed all
three probes: 48,000 decoded PCM samples and successful x86_64/i386 Wine bridge
checks. The direct-import audit of 31 Wine Unix modules then reported zero
unresolved libraries. The plain same-ABI FFmpeg build had failed the bridge probes
before the re-export fix; file presence alone would have missed this regression.
