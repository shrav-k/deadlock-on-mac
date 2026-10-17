# Wine startup and exit fixes: build, test, activate and roll back

The current `highball-hotfix-v2` overlay contains the existing sechost exit fix
and four upstream WinMM patches for a reproduced Steam audio-enumeration stall.
It has native API and menu/lifecycle qualification; audible game audio, gameplay
performance and current display/input acceptance are separate gates. See the
[recorded startup investigation](STARTUP-INVESTIGATION.md). No original engine
file is replaced and no audio driver is disabled.

Keep the earlier display failure in the record: 1920×1200 exclusive fullscreen
produced a size mismatch/black screen on exit. A subsequent 1512×982 borderless
run displayed and quit normally. Audio/startup fixes do not repair that exclusive
fullscreen behavior by implication.

The installed Highball Wine 11 engine lacks two upstream device-notification
handle fixes. A previous Deadlock exit fault was in
`sechost!I_ScUnregisterDeviceNotification`. These upstream patches guard invalid
handles and prevent removing an invalid list entry:

- [d8aa0abfb592](https://github.com/wine-mirror/wine/commit/d8aa0abfb5923e4d0cbbb659e13f9f8f7c5c9ee0)
- [f38f3ac7708f](https://github.com/wine-mirror/wine/commit/f38f3ac7708f93ceaf1ff2404690bd4c8d88d6d0)

`config/wine-hotfix.json` pins the CrossOver LGPL source archive, exact Highball
recipe snapshot and every patch, LLVM-MinGW, Bison, and reviewed output hashes.
`patches/wine/` retains upstream authorship and complete patch text. The build
applies only the reviewed `dlls/sechost/service.c` and `dlls/winmm/waveform.c`
changes. Separate native probes cover device-notification handles and audio
formats in both Windows architectures. The WinMM series enables AUTOCONVERTPCM,
accepts supported formats requiring conversion, preserves non-PCM decoding and
removes enumeration-time probing. All four prerequisites are retained; see
[upstream research](GITHUB-RESEARCH.md#winmm-enumeration-and-steam-startup).
These are upstream backports, not original fixes authored by this project.

## Build

Install Command Line Tools, Python 3.12+, and the normal pinned runtime first.
Homebrew is not required by this build recipe. The current output was reproduced
using Xcode 27.1 / macOS SDK 27.0 / Apple clang 21.0.0 plus the pinned LLVM-MinGW
compiler. Command Line Tools may build it, but another SDK/toolchain must match
the expected bytes or undergo separate review.

```sh
python3 bin/deadlock-mac runtime-install --runtime highball
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer python3 packaging/build_wine_hotfix.py \
  --workspace "$PWD/.." --build-dir "$PWD/../Tools/wine-hotfix-build"
```

Use a new build directory; the script refuses to overwrite previous outputs.
It builds only `sechost.dll` and `winmm.dll` for x86_64 and i386, compares their exports against the
original engine, checks reviewed hashes, retains `COPYING.LIB` and source
provenance, and stages the result under `Runtimes/highball-hotfix-v2`. Activation
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
python3 packaging/check_audio.py --workspace "$PWD/.." \
  --compiler-bin /absolute/path/to/llvm-mingw/bin --profile highball
python3 bin/deadlock-mac launch
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

With Windows Steam closed, restore the pinned exit-only revision (original audio
behavior) or disable all overlays:

```sh
python3 bin/deadlock-mac wine-hotfix --set previous
# Or disable all overlays:
python3 bin/deadlock-mac wine-hotfix --set off
# Select current again:
python3 bin/deadlock-mac wine-hotfix --set on
```

`previous` and `off` are explicit choices that subsequent setup preserves. An old
v1 receipt without an explicit pin remains usable and is upgraded only by requested
setup or selecting `on`, not by a routine launch. Missing/corrupt new payloads never
replace a valid previous receipt. Both revisions require the exact pinned runtime.
Before opening an older manager app that only knows v1, select `previous` with the
current CLI. App rollback alone does not roll back independently stored runtime state.

Fresh bootstrap uses a verified local/bundled hotfix. The packaged preview includes
both current and exit-only rollback payloads, so selecting either requires no
compiler. Source-only setup without a built payload prints its absence; build the
pinned recipe before Steam setup. No unreviewed replacement is downloaded.

## Distribution

For a local app preview, pass `--wine-hotfix ../Runtimes/highball-hotfix-v2` to
`packaging/build_app.py`. The small overlay, license and provenance are included;
new setup stages and verifies them before Steam initialization. The packaged
onboarding test exercises fresh installation, repeat setup, legacy upgrade,
explicit previous-revision rollback and opt-out in a temporary empty workspace,
without launching Wine or downloading a game. A public release
must accompany LGPL binaries with corresponding source, patches and build
instructions as required by their license, and complete the dependency license
review. No public hotfix binary release has been published. Original Wine and
CodeWeavers notices remain applicable; the DLLs are not MIT-licensed manager code.
