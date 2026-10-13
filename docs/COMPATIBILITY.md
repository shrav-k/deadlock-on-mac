# Compatibility ledger

Keep observed results distinct from upstream claims. Last updated 2026-10-13.

| Configuration | Installation | Steam account | Deadlock rendering | Multiplayer / Cloud |
| --- | --- | --- | --- | --- |
| M2 Max, 32 GiB, macOS 26.6.2; Highball Wine 20261006 + DXMT a444716 | Steam and Deadlock build 25841406 installed, including a clean installation | User confirmed sign-in in both installations and restart after relocation | User confirmed original gameplay and fresh-install Hero Sandbox; startup/exit faults remain | Not yet tested |
| Same Mac; Wine Sikarugir 11.0_1 + DXMT 0.80 | Steam installs and self-updates | Login UI stays black, including software rendering | D3D11 probe passes; game not tested | Not tested |
| Same Mac; official CrossOver 26.3.0 | App signature and notarization verified; trial opens | Not yet tested | Not yet tested | Not yet tested |

Manager: automated unit and lifecycle tests pass locally on Python 3.13.2. These are not game
compatibility tests. The CrossOver trial started 2026-10-13; no purchase was made.

Both free-runtime probes reported Apple M2 Max, feature level 11.0, successful
device/swapchain creation, and 120 successful Present calls. This establishes API
operation, not visually verified game output. The Steam client updated itself to
build 1788652215. Highball login was confirmed by the user; this session's macOS
UI tool cannot enumerate the Wine windows. Account credentials were not inspected.

## Open failures and package audit

The user observed Wine's Program Error for `deadlock.exe` during the first launch.
A Deadlock assertion dump and separate Steam/overlay dumps were preserved locally.
The captured access violation was in Steam's `sechost.dll` during a shutdown
request; it does not establish the game-crash cause. A second diagnostic launch
was stopped at the user's request before consolidation.

After consolidation, a stale Wine temporary loader-cache symlink still referenced
the old runtime location. With the profile stopped, only the cache with that
verified stale target was archived. Wine rebuilt it; a Windows command probe then
succeeded and the user confirmed Steam was visible after a cold client restart.
The manager now reports an immediate nonzero loader exit instead of returning a
PID as though launch succeeded. Automatic workspace relocation remains unimplemented.

On the next game launch, the user confirmed a visible main menu or game. Wine
logged virtual-memory allocation failures, but the game remained alive and macOS
reported normal memory pressure; physical RAM exhaustion is not established.
A new Deadlock assertion dump had no exception stream. At approximately 11:35
Pacific, Wine logged a write-access fault and the original game process exited.
The user confirmed deliberately quitting and relaunching the game; the new game
process remained running. The user later confirmed gameplay, jitter and occasional
FPS dips on the built-in display, then deliberately quit again. These were observed
exit-path faults, not evidence of unexpected gameplay crashes during those attempts.
Sustained gameplay, input/audio,
multiplayer and Cloud behavior still need acceptance testing.

A direct Mach-O dependency scan of the Highball engine's 31 Unix modules found
`winedmo.so` references missing Intel Homebrew FFmpeg libraries: `libavformat.63`,
`libavcodec.63` and `libavutil.61`. GStreamer libraries/plugins are present and the
manager now sets their search paths, but the game's video path has not been
verified. This dependency gap must be resolved or explicitly tested as an optional
fallback before a player release. Do not substitute dylib ABI versions with symlinks.

After consolidation, all 5,641 files/links in the Highball Wine, paired DXMT and
support installations matched their pinned archives. Steam metadata and dry-run
launch paths point inside the new workspace. An offline backup of 52 Deadlock data
files was created and its per-file hashes verified. Recovery has not been tested.

## Clean installation and performance test

The local SwiftUI app bootstrapped an empty workspace using its bundled Python,
downloaded and verified the pinned runtimes, installed Windows Steam, and reached
the login form after the client updated. The user confirmed sign-in and a fresh
Deadlock download. Initial delay before the Steam window appeared was not a
confirmed black-window failure. The fresh runtime's 5,641 files/links matched the
archives. After a second verified backup containing 55 game-data files, the user
authorized deletion of the old game installation and failed comparison bottle.
The fresh bottle was moved into the main workspace without copying the game;
duplicate runtime/download directories were removed. No Steam login data was
included in the game-data backup.

The first fresh game launch requested 1920×1080 fullscreen via Steam arguments,
with the DXMT 60 FPS cap and Metal HUD enabled. It exited before presenting any
game HUD samples. Wine logged an access violation at
`I_ScUnregisterDeviceNotification+0x34` in `sechost.dll`. The assertion dump had no
exception stream and Wine's debugger could not recover a backtrace. The same
function also faults during normal exits; the initial startup cause remains unknown.

A normal Steam retry, with the cap/HUD unchanged and no forced display arguments,
reached the menu. The user confirmed Hero Sandbox and usable gameplay. This is
recovery evidence, not proof that fullscreen arguments caused the first failure.
The tested display was **1512×982 borderless, 120 Hz**, with a saved render scale of
approximately **73%**, AC power and Low Power Mode off. The screenshot identified
DXMT a444716, D3D11 feature level 11.1, about 59 FPS and Game Mode off.

During approximately five minutes after the sandbox-start confirmation, recorded
presentation samples had a 16.67 ms median/p95 and a 25 ms p99. The user reported
small dips and then **Mina's ultimate (summoning bats) dropping to 40 FPS or below**,
with rapid perceived heating. That ability is the next repeatable stress case.
Long gaps in the log, including possible focus changes, prevent treating its overall
average as a gameplay FPS benchmark. The test ended before the planned warm-up and
controlled comparison finished. This does **not** pass steady 60 FPS or 1080p acceptance.
`pmset` reported no recorded thermal/performance warning; it did not establish a
temperature or rule out throttling. After the user quit normally, Wine logged the
same cleanup fault despite the game window appearing to close normally.

Upstream Wine has two relevant fixes for invalid device-notification handles:
[argument validation and fault handling](https://github.com/wine-mirror/wine/commit/d8aa0abfb5923e4d0cbbb659e13f9f8f7c5c9ee0)
and [skip removal when the handle is invalid](https://github.com/wine-mirror/wine/commit/f38f3ac7708f93ceaf1ff2404690bd4c8d88d6d0).
The installed binary's disassembly lacks these guards. A source backport was subsequently built and tested as described below; it does
not establish that every startup/display/exit fault is resolved. Do not mix an arbitrary newer
`sechost.dll` into the current runtime.

The subsequent run applied 1512×982 fullscreen in the game's settings while
preserving the approximately 73% scale and 60 FPS cap. The user initially reported
a crash, then corrected it to minimization. The pasted debugger report belonged to
the previous game's exit fault; the current game remained running without a new
fatal exception. Its settings enabled minimize-on-focus-loss. After repeating
Mina's ultimate, the user reported a low of **51 FPS with stutter**, and Game Mode
remained off. Shader caches were warmer in this second run, so this is not an
isolated causal measurement of fullscreen versus borderless. It still does not
meet the steady-60 target. A lower-render-scale comparison was proposed but not
performed; testing switched to Game Mode.

Later screenshots showed advanced FSR2 (TAA) at 1.5×, AO off, medium shadows and
textures, low fog, and post-process bloom on. Saved configuration values can lag
the live UI. The user set both in-game and dashboard FPS limits to 60 (the UI's
minimum), reporting little improvement from that change alone.

On the same running game, Apple's compatible, signature-verified `gamepolicyctl`
temporarily forced the system-wide Game Mode policy on. The tool, macOS service
log and user-observed Metal HUD all confirmed activation. At approximately 12:47
Pacific, the user reported **Mina's bat ultimate staying around 60 FPS, with the
earlier stutter gone**. Renderer and output resolution were unchanged for this
comparison. This remains a short, user-observed sandbox result with a warmer cache,
not a controlled causal benchmark or sustained-match/1080p acceptance. The mixed
HUD interval retained focus gaps and some intervals above 16.67 ms; it does not
establish perfect frame pacing. The optional bounded diagnostic is documented in
[PERFORMANCE.md](PERFORMANCE.md). Native macOS recognition of the Wine game remains
unimplemented; the manager now provides a separate lifetime-based Play watcher.

The user subsequently reported successful testing at **1920×1200 with Game Mode
on**. Exact frame statistics, duration and quality settings for that resolution
were not independently established. At 12:53:50 Pacific the game process ended;
the temporary guard detected this and restored automatic policy, with the Apple
tool confirming Game Mode off. This validates that live diagnostic's normal
cleanup, not the separate cold-launch or exit-fault fixes.

### Automatic Play lifecycle — 2026-10-13

Normal manager Play now starts a detached Game Mode watcher. A live source-CLI
launch at 13:10:28 Pacific saved `auto`, enabled `on`, asked Windows Steam to
launch Deadlock, and matched its actual game process in the Highball bottle. The
user confirmed Game Mode On. Wine faulted and kept the game process alive in its
debugger; Game Mode stayed on beyond five minutes. After the user closed the error
and debugger windows, the watcher detected process exit at 13:16:10 and restored
`auto`; a separate Apple-tool check confirmed mode off. This validates lifecycle
behavior, including a debugger-held process, not six minutes of stable gameplay.

Automated lifecycle cases cover simulated multi-hour play, restoring `auto`/`on`/
`off`, startup timeout, failed launch/enable, PID reuse, concurrent workers,
interrupted-session adoption, failed restoration and explicit cancellation.
The rebuilt native app retains the selected Apple tool and defaults its Play
option on. Native macOS game classification and the existing Wine exit fault
remain unresolved.

For each live result add: date, macOS/chip/RAM, engine and graphics versions,
Deadlock build ID, resolution/settings, test duration, what worked, what failed,
and whether the test was observed directly or reported by another user. Do not
include account IDs, passwords, tokens, full local paths or unredacted logs.


### Matched-source exit backport and newer Wine — 2026-10-13

The reviewed `highball-exitfix-v1` overlay builds both sechost architectures from
the exact Highball source/patchset plus the two upstream validation fixes.
Independent build directories produced byte-identical DLLs after normalization;
both preserve the original 208-entry export ABI. Both API probes passed null,
readable-invalid and inaccessible handle cases with exact errors, plus a valid
register/unregister cycle. The hardware D3D11 120-frame probe also passed. Base
runtime files were not modified. See [build provenance](WINE-HOTFIX.md).

The separate Gcenx Wine 11.18 macOS candidate initialized a fresh disposable prefix
and passed both API probes. No Steam account or game install was copied. Steam,
DXMT and Deadlock compatibility on that candidate remain untested. Upstream 11.19
source is newer than the selected macOS binary channel; no automatic promotion
occurred.

The first patched Steam/game launch at 13:47 Pacific used the saved 1920×1200
fullscreen settings. The user reported a size mismatch and black screen on exit.
The game process subsequently disappeared and Game Mode restored, but the UI
failure means this is not a passing quit test. At the user's request the remaining
Wine environment was stopped and restarted. That failure is not attributed to a
specific patch without a controlled comparison.

After a backed-up return to 1512×982 borderless, the 14:03 launch reached the game.
The user confirmed normal picture and clean in-game quit without the debugger.
The process disappeared, its launch log contained no unhandled exception/page-fault
backtrace, and independent Apple-tool status confirmed `auto`/off restoration.
This is one successful in-game quit, not the ten-cycle/soak release gate.

A later brief capture smoke test collected 765 HUD presentation samples from the
real game's stderr log and verified Game Mode On at the boundary. This validates
recording integration only; it is not a gameplay benchmark or stable-60 claim.


The subsequent manager Exit test also completed: `taskkill` without `/F` requested
normal close, the game process exited, Windows Steam stayed open, and the watcher
restored `auto`. This is a separate successful manager-close cycle. Fullscreen
qualification continues; borderless recovery is a fallback, not the final target.

A standalone DXGI geometry probe successfully entered/restored 1512×982 and
1920×1200 fullscreen with matching client, backbuffer and desktop dimensions.
`FindClosestMatchingMode` mapped its 1920×1080 request to 1920×1200, so exact 1080p
was not counted as a pass. Native API geometry alone does not prove visible
coverage, focus behavior, or Deadlock correctness. The first probe revision used
an incorrect resize ordering and timed out; it is not evidence against the runtime.

The 14:17 Pacific cold launch requested 1920×1200 fullscreen after clearing the
saved borderless flag. The user still observed cropping/blank space and reported
being unable to switch away until the game exited. The game later saved
`nowindowborder=1` again. Clearing that flag is therefore not a validated fix or
an established explanation of the defect. At 14:39 the process ended and Game
Mode restored to `auto`; no unhandled exception was found in that run's saved log.

The user accepted high-resolution borderless as an alternative. With Steam and
Wine stopped, enabling `RetinaMode=y` changed the probe's reported desktop from
1512×982 to 3024×1964 at 120 Hz. Both mode-list probes exited successfully and
preserved their starting desktop. Deadlock was launched through Steam at 14:42
with 3024×1964 borderless and Game Mode on. The user confirmed that the picture
fills the screen, pointer clicks align and Command–Tab away/back works. The user
did not separately confirm the HUD dimensions; saved output dimensions and the
Wine desktop probe are 3024×1964. No fullscreen fix, external-display support or
sustained native-resolution frame rate is claimed.

The manager's next normal-close request at 14:52 timed out after 30 seconds. The
process subsequently exited and Game Mode restored to `auto` at 14:53:49. No fatal
exception was found in the saved launch log. The user confirmed using the game's
Exit Game option and that it closed normally. This is a successful in-game exit
with Retina enabled, but not a clean manager-exit pass: its earlier request did
not complete on its own.

After Steam closed, the saved game/menu caps were still 400/120. Both were changed
to 60 with an exact configuration backup; the 3024×1964 borderless settings were
preserved. The engine's requested FPS limit alone was therefore not sufficient
evidence of the game's saved cap. Verification after relaunch is pending. These
later runs use Steam-updated game build 25917577; earlier build 25841406 results
must not be treated as a controlled same-build comparison.
