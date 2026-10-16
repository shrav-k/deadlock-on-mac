# Wine exit hotfix: build, test, activate and roll back

This remains a **candidate** with limited live acceptance. A subsequent 1512×982
borderless run displayed normally and the user confirmed a clean normal quit.
The game process exited, no fatal exception was logged, and the watcher restored
automatic/off Game Mode. Repeated cycles and fullscreen still need qualification.

The initial live
1920×1200 fullscreen run reached the menu but the user reported a display-size
mismatch and a black screen on quitting. Its game process later disappeared and
Game Mode restored, but clean exit acceptance failed. Keep that failure separate
from the passing API probes.

The installed Highball Wine 11 engine lacks two upstream device-notification
handle fixes. A previous Deadlock exit fault was in
`sechost!I_ScUnregisterDeviceNotification`. These upstream patches guard invalid
handles and prevent removing an invalid list entry:

- [d8aa0abfb592](https://github.com/wine-mirror/wine/commit/d8aa0abfb5923e4d0cbbb659e13f9f8f7c5c9ee0)
- [f38f3ac7708f](https://github.com/wine-mirror/wine/commit/f38f3ac7708f93ceaf1ff2404690bd4c8d88d6d0)

`config/wine-hotfix.json` pins the CrossOver LGPL source archive, exact Highball
recipe snapshot and every patch, LLVM-MinGW, Bison, and reviewed output hashes.
`patches/wine/` retains upstream authorship and complete patch text. The build
applies only their `dlls/sechost/service.c` changes; the separate native probe
covers invalid and valid notification handles in both Windows architectures.
These are upstream backports, not original fixes authored by this project.

## Build

Install Command Line Tools, Python 3.12+, and the normal pinned runtime first.
Homebrew and full Xcode are not required by this build recipe.

```sh
python3 bin/deadlock-mac runtime-install --runtime highball
DEVELOPER_DIR=/Library/Developer/CommandLineTools python3 packaging/build_wine_hotfix.py \
  --workspace "$PWD/.." --build-dir "$PWD/../Tools/wine-hotfix-build"
```

Use a new build directory; the script refuses to overwrite previous outputs.
It builds only `sechost.dll` for x86_64 and i386, compares their exports against the
original engine, checks reviewed hashes, retains `COPYING.LIB` and source
provenance, and stages the result under `Runtimes/highball-exitfix-v1`. Activation
is separate. A changed compiler/SDK/output must be reviewed, not accepted by
rewriting the expected digest automatically.

All Highball patches are essential: its GS-slot LastError patch changes inline
Windows API behavior. Building plain CrossOver source fixed the access violation
but returned incorrect error values when mixed with Highball. The matched build
passes both architectures. Two builds in separate paths produced identical DLLs
on this Mac after source/debug path normalization, fixed timestamps, debug
stripping and disabling path-dependent PE build IDs. This is not a reproduced
build of the entire engine, nor proof of reproducibility on other SDKs.

## Activate and test

Exit Windows Steam and other Wine bottles, then:

```sh
python3 bin/deadlock-mac wine-hotfix --set on
python3 bin/deadlock-mac wine-hotfix
python3 packaging/check_runtime.py --workspace "$PWD/.." \
  --compiler-bin /absolute/path/to/llvm-mingw/bin --profile highball --graphics
python3 bin/deadlock-mac launch --game-mode-tool /absolute/path/to/gamepolicyctl
```

Both handle probes must pass, including exact error codes and a valid
register/unregister cycle. The graphics probe must create a hardware D3D11 device
and present 120 frames. Then test Steam, the game, normal quit, manager Exit,
Game Mode restoration, and relaunch. The original Wine files remain intact; a
verified process-local DLL search overlay supplies the hotfix. Steam must restart
because games inherit its environment. Hashes are checked before launches.

The manager's **Exit Deadlock** button / `exit` command asks the running Steam
client to stop app 1422450 through its non-forced `+app_stop 1422450 0` command,
waits for actual process exit, then checks Game Mode restoration. It leaves Steam
open for synchronization. The earlier Wine `taskkill`/`WM_CLOSE` path did not
reliably close the game and is not the current exit implementation. A timeout is a failure,
not permission to kill the game. Forced recovery remains an explicit operator
choice; it is not a passing exit test.

Roll back with Windows Steam closed:

```sh
python3 bin/deadlock-mac wine-hotfix --set off
```

Fresh bootstrap uses an available verified local/bundled hotfix. It respects an
explicit rollback. Source-only setup without a built payload prints its absence;
it does not silently download an unreviewed replacement.

## Distribution

For a local app preview, pass `--wine-hotfix ../Runtimes/highball-exitfix-v1` to
`packaging/build_app.py`. The small overlay, license and provenance are included;
new setup stages and verifies them before Steam initialization. A public release
must accompany LGPL binaries with corresponding source, patches and build
instructions as required by their license, and complete the dependency license
review. No public hotfix binary release has been published. Original Wine and
CodeWeavers notices remain applicable; the DLLs are not MIT-licensed manager code.
