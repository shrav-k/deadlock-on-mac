# Compatibility ledger

Keep observed results distinct from upstream claims. Last updated 2026-10-16.
The dated entries below preserve historical results and failures; later entries
describe fixes and current qualification limits.

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
evidence of the game's saved cap. After the full Steam restart and 14:58 game
launch, the user confirmed all acceptance checks: full screen coverage, aligned
pointer clicks, Command–Tab away/back, HUD output of 3024×1964, Game Mode On, and
both game/menu limits at 60. This supersedes the earlier uncertainty about HUD
dimensions. A short setup capture averaged approximately 60 presentation FPS;
it is not a gameplay stress test or a sustained-match result.

The user paused gameplay testing before the Mina Hero Sandbox comparison at
these settings. Resume that comparison only when requested. Fullscreen coverage
and focus, manager Exit reliability, external displays and full-match performance
remain open. These later runs use Steam-updated game build 25917577; earlier build
25841406 results must not be treated as a controlled same-build comparison.

## Manager shutdown correction — 2026-10-13

The earlier manager timeout used Wine `taskkill` without `/F`, which posts
`WM_CLOSE` and reports message delivery even when the application remains open.
The installed Steam client exposes `app_stop <appid> [force:0|1]`. Replacing the
window message with `steam.exe -ifrunning +app_stop 1422450 0` closed Deadlock in
the initial menu-only investigation and let the watcher restore `auto`.

Five subsequent cold-Steam launch/exit cycles passed using the 0.2.0 app's bundled
CLI. Each cycle verified one running game with Game Mode On, actual game exit,
restoration to the original `auto` policy, Steam remaining open, normal Windows
Steam/helper shutdown, and repeated no-op Exit commands. Exit plus restoration
took approximately three to five seconds. No gameplay input was sent. Private
evidence is in `DeadlockData/lifecycle-checks/20261013T221750782425Z/`.

This supersedes the failed manager-close path for this tested stack; it does not
establish every Wine/CrossOver build or hung/crashed-game recovery. Steam commands
can change with client updates, so the manager verifies actual exit and reports
timeouts rather than treating command delivery as success. A separate regression
test covers helpers lingering after the main Steam client has already exited.

The Python suite has 112 passing tests, including shutdown/error/isolation and
packaging failure cases. Native Swift quit-policy tests pass. One additional
lifecycle cycle passed after installing the final bundle, with exit/restoration
in 6.3 seconds; its report is in
`DeadlockData/lifecycle-checks/20261013T222309993556Z/`.

After unlocking the Mac, the user confirmed clicking **Quit Manager** closed its
window. A subsequent process check confirmed the manager executable was no longer
running; the Game Mode receipt remained finished, at `auto`, with no restoration
pending. This is a verified idle Quit button check. The UI tool continued to lose
its native connection, so direct button checks for Exit Deadlock/Windows Steam,
Command–Q, window-close and quit during an active operation remain distinct from
the passing shared-CLI and Swift policy tests. Gameplay and external-display
acceptance remain paused; the fullscreen defect remains unresolved.

## Actual manager controls — 2026-10-14

The user clicked the installed 0.2.0 app's **Exit Deadlock** button. The game process
disappeared, Steam stayed open, and the session receipt confirmed restoration from
the prior `auto` policy to `auto`/off with no pending recovery. **Exit Windows Steam**
also passed through its actual button: the client and browser/service/overlay
helpers disappeared while the manager remained open. An idle **Command–Q** check
closed the manager window and its process. These are distinct from the earlier
shared-CLI checks. The UI-control service still failed, so the user performed the
interactions while process/receipt checks supplied independent evidence.

The subsequent **red close during Exit Windows Steam** check failed: a timestamped
process capture showed the manager disappear while its Python shutdown worker was
still running and reparented; Steam remained open. This invalidates the earlier
inference that the passing quit-policy tests established the actual window path.
The 0.2.1 correction gives AppKit ownership of the window, strongly owns the model
in its delegate, and resubmits busy quit requests only after successful completion.
Eight native integration cases pass with isolated workers, including actual AppKit
close-button dispatch, failed operations and diagnostic cancellation. Live retest
of the rebuilt app is tracked separately; no gameplay is part of these checks.

Private UI evidence is under `DeadlockData/ui-acceptance/2026-10-14/`. External
hardware detected in this session is an LG UltraGear at 2560×1440/144 Hz on HDMI,
with the built-in display still primary. The user's intended use is many displays
while hotdesking; this hardware detection is not an external gameplay pass.

The 0.2.1 live retry did **not** pass Steam shutdown. The user reported that Steam
remained open and the manager appeared stuck. The worker ran for approximately
60 seconds, then exited while the manager remained alive. A native process sample
showed the manager servicing its main event loop. This differs from 0.2.0's
premature termination, but does not meet the requested end-to-end behavior.

Steam applied a pending update during the intervening restart: its updater changed
from a September 2 build to October 13, with client build 1791918634. Subsequent
`-ifrunning -shutdown` requests, and a diagnostic request without `-ifrunning`,
returned zero without a corresponding `ExecCommandLine` in the client log. A Wine
relay trace showed the command being written to `TempAppCmdLine` and a successful
`SetEvent` on `Global\\Valve_SteamIPC_Class`; this establishes submission, not
client processing. The update is a correlation, not a proven root cause. No
Steam downgrade, force kill or gameplay test was performed. A Steam-menu exit and
fresh-client comparison remain pending.

Operation status and the latest progress/error line now appear beside the Exit
buttons, with elapsed time and periodic shutdown countdown messages. The timeout
explains how to use Steam's own Exit and that the manager can be quit afterward.
113 Python tests and nine native app integration tests pass locally, including
an explicit quit after an operation fails. These do not resolve or qualify the
remaining live Steam IPC failure.

The user then reported Steam's own **Steam → Exit** stuck on “Exiting.” Before
recovery, Deadlock was absent, Game Mode was restored to `auto`, and Steam's last
Cloud log reported synchronization complete. After preserving private logs and
process samples, the affected bottle was force-stopped explicitly for recovery.
This was not a normal-exit pass and is not an automatic manager fallback. Native
Mac Steam and game files were untouched.

A cold start of the same client build 1791918634 subsequently processed the normal
`-ifrunning -shutdown` request and exited with all helpers. No version rollback or
client patch was applied. This demonstrates recovery from the stuck session,
not a proven fix for the cause. The 0.2.2 manager bundle was installed with its
signature verified; the idle old manager was terminated for replacement, which
is not counted as a Quit-button test. Longer idle/client shutdown checks and
actual busy-close/Command–Q acceptance remain separate gates.

The subsequent Steam-only check waited 180 seconds, including a successfully
completed background update check, before requesting shutdown. The client and
helpers exited normally in **2.56 seconds**; a repeated shutdown was a successful
no-op, and Game Mode stayed at `auto`. The report is
`DeadlockData/lifecycle-checks/20261014T232424909041Z/report.json`. This is a second
successful shutdown after recovery, not gameplay or update-handoff qualification.
The suite now has 117 passing Python tests, including Steam-only harness guards
against launching or closing a user-started game. Both GitHub Actions runs for
commit `8671bfd` passed, including the nine native AppKit integration scenarios.

### Final 0.2.2 busy-quit acceptance

Both remaining actual controls passed after recovery. The user performed the
actions; a timestamped process trace independently verified shutdown order:

| Action during Exit Windows Steam | User observation | Process result |
| --- | --- | --- |
| Red window-close button | Manager waits, then Steam and manager close | Steam and all helpers were absent by 23:28:38.111 UTC; the manager and its still-owned worker remained until completion |
| Command–Q with manager focused | Manager waits, then both close | Steam and all helpers were absent by 23:29:32.718 UTC, the worker by 23:29:33.013, and the manager by 23:29:33.331 |

Neither check launched Deadlock or used force termination. The worker remained a
child of the manager while shutdown was in progress. Game Mode remained at the
previous `auto` policy with no restoration pending. Private receipts are
`busy-close-0.2.2.json` and `busy-command-q-0.2.2.json` alongside
`process-transitions-0.2.2.jsonl` in the UI evidence directory above.

Together with the earlier actual Exit Deadlock, Exit Windows Steam, idle Quit
Manager and idle Command–Q checks, this completes the requested manager-control
acceptance on this stack. Four normal Steam shutdowns passed after the one scoped
recovery. The cause of the earlier Steam update/session hang remains unresolved;
these results do not establish that it cannot recur. External-display coverage,
focus, gameplay and sustained performance remain separate acceptance work.

## 0.3.0 display picker — 2026-10-14

The named LG ULTRAGEAR preparation selected SDL monitor index 1 and configured
2560×1440 borderless with Retina off. Native host inventory before/after retained
the built-in screen as primary and the LG at 2560×1440@144 Hz, origin (1512,-458).
The owned D3D11 grid returned client/buffer 2560×1440 and closed normally. No
corner-click events were received in the initial timed run, so input/visual
acceptance is not claimed. The following menu-only launch through signed-in
Windows Steam created a Deadlock process, enabled the Game Mode watcher and
produced game-specific Metal HUD samples. The normal manager CLI Exit request closed PID 65924 without forced termination;
the watcher confirmed prior Game Mode policy `auto` restored with no pending
recovery. Actual button/menu placement, pointer alignment and Command–Tab
confirmation are pending; gameplay remains paused.

User follow-up: **no Deadlock window was ever visible**. This is a failed visual
launch check, despite the process/Metal evidence and clean CLI shutdown. The grid
was also unseen or missed before its old 90-second timer expired. Do not promote
this display configuration as visually verified.

Automated coverage includes selection and missing/ambiguous displays, negative
coordinates, reordered indices, Retina mapping, changes during preparation,
rollback, SDL/configuration updates, disabled management and actual input-evidence
parsing. Native picker-model tests and all nine AppKit lifecycle scenarios pass.

## 0.3.1 activation candidate and diagnostic lifecycle — 2026-10-14

The manager now responds to the selected Wine engine's cooperative activation
request during a foreground, user-initiated launch. Automated tests verify prefix
and executable guards, expiry, background rejection and duplicate-PID handling.
No actual macOS activation/visible-LG success is claimed yet.

The grid now uses a parent-owned stdin control pipe with no observation timer;
Escape/Close, Stop Grid or manager quit ends it. The first real Highball control
check rejected `PeekNamedPipe` on inherited Unix stdin. Switching the owned helper
to `ReadFile` on a separate thread passed the real Wine check: ready, parent pipe
closed, child result 0, normal bottle shutdown. No window, Steam, game or Game
Mode change was involved. Reproduce after helper/runtime changes with:

```sh
python3 packaging/build_display_tools.py --downloads ../Downloads
python3 packaging/check_display_control.py --workspace .. --profile highball
```

141 Python tests, 12 native AppKit lifecycle scenarios, the display model,
activation eligibility and lifecycle policy tests pass locally. Actual LG grid
coverage/clicks/Command–Tab, game menu placement and button exit were pending at that checkpoint.

Follow-up 0.3.1 user acceptance: the grid appeared on the LG and its edges, corner
click alignment, Command–Tab and Stop Grid worked. The macOS menu bar remained
visible while the pointer was centered. Worker/helper/server processes ended,
but no completed log was saved; do not attribute old 0.3.0 events to this run.
Game-menu acceptance on the LG remains pending.


## Xcode qualification and 0.4.3 lifecycle candidate — 2026-10-16

Official Xcode 27.1 (27A9275) completed first-run setup on macOS 26.6.2. Fresh
packaged dependency preparation passed without an existing tool cache or manual
override; the bundled FFmpeg installation also passed. See
[Game Mode setup](GAME-MODE-SETUP.md) for the exact scope and private-API limit.
The suite has 192 passing Python tests; 13 native AppKit lifecycle scenarios and
the display/activation policy checks passed using the new compiler.

The first live lifecycle run found a normal-shutdown race: Steam processes had
exited but Wine's server remained during its persistence grace period. The next
display check correctly refused that still-active session. Version 0.4.3 waits
for the selected prefix's server to finish using `wineserver --wait`, with a
bounded timeout and no forced termination. Three consecutive source-CLI cycles
then launched Deadlock, closed only the game, restored `auto`, and closed Steam
and Wine. Game Exit took 3.21, 3.66 and 3.24 seconds. Steam updated the game to
build 25997478. These are process/lifecycle results, not visible-menu or gameplay
acceptance. Private receipt: `DeadlockData/lifecycle-checks/20261016T222920728796Z/report.json`.

The built-in and LG inventories agreed across Windows monitor, display-mode and
GDI APIs with Retina both off and on. No additional GDI doubling was observed;
the global Retina policy still doubles the 1× external display when enabled.
See [the upstream review and probe result](GITHUB-RESEARCH.md). This does not
resolve the remaining fullscreen/pointer/focus acceptance work.

The rebuilt manager's actual Quit button closed its process. Its actual Play
button sent the Steam launch request, but the first built-in/Retina-On run did
not produce a Deadlock process: Steam logged a fatal stalled cross-thread pipe.
The watcher timed out and restored `auto`. A retry logged a stalled Steam main
loop; the test was cancelled and policy restoration verified. The manager's
“Play request sent” status acknowledges dispatch only; it does not show later
watcher failure. Startup status reporting and this cold-start failure remain
open. Do not label 0.4.3 fully qualified from the earlier CLI passes.

A subsequent packaged-CLI run with the manager closed and the same built-in
Retina configuration also failed to start the game. This rules out the manager
UI as a necessary trigger; it does not isolate Retina as the cause. Policy
restored to `auto`, and Steam/helpers exited without force termination. Private
receipt: `DeadlockData/lifecycle-checks/20261016T224402327160Z/report.json`.

The computer-control service also crashed while inspecting the manager's
Settings view (`SkyComputerUseService`, an array-removal assertion), and its app
inventory did not expose the Wine windows. These are separate automation limits,
not proof of a locked Mac or of successful visual output. No current-session
sandbox/performance result is claimed. The remaining gates are in
[AUTONOMOUS-TESTING.md](AUTONOMOUS-TESTING.md).

The final packaged 0.4.3 CLI comparison with LG selected and Retina Off passed:
Deadlock started through Steam, normal game exit restored `auto`, and Steam plus
Wine finished shutdown. Private receipt:
`DeadlockData/lifecycle-checks/20261016T224804332197Z/report.json`. This is a
lifecycle pass only. It narrows the observed configuration difference but does
not prove Retina caused the earlier startup failures. The LG remains prepared
at 2560×1440; the built-in display remains macOS primary. All test game/Steam
processes ended, no restoration is pending, and the temporary keep-awake
assertion was released. No permanent lock/password setting changed.

## 0.4.4 startup and shutdown investigation — 2026-10-16

Built-in Retina On subsequently started through source CLI, packaged CLI and the
actual manager Play button. The earlier Steam main-loop stall is intermittent;
Retina has not been isolated as its cause and no engine fix is claimed.
See [the investigation and per-run evidence](STARTUP-INVESTIGATION.md).

The manager now shows the detached watcher's startup/result and restoration on
the Play page. A current launch-log tail supplies a more specific error only
after startup times out; a recoverable warning cannot abort a running game.
Shutdown checks now include the 64-bit Steam overlay and briefly recheck a helper
whose cwd disappears during exit. Persistent ownership ambiguity remains an error.
Orphan overlay cleanup, when needed after all owners exit, is reported separately
from normal shutdown and never targets the game, client or whole Wine server.

207 Python tests and the native AppKit/display/activation/status-reader checks
pass. Sixteen synthetic view snapshots cover two widths and light/dark modes;
review exposed and corrected clipped display-help text. Packaged fresh FFmpeg and
Xcode Game Mode preparation pass without a pre-existing tool cache. Two LG cycles
and two subsequent built-in Retina cycles pass startup, normal game/Steam/Wine
exit and exact restoration; all four overlays exited normally. These are lifecycle
results, not visual or gameplay acceptance, and do not exercise automatic orphan
recovery. The actual Play page displayed the new running-process status.

The computer-use service still fails when inspecting Settings/Diagnostics and
does not expose Wine windows. Steam/game screenshots, pointer/focus checks and
private-sandbox performance remain blocked by that UI access. No blind gameplay,
public matches, new renderer or speculative Retina patch was used. The remaining
autonomous/replay/visual test flow is in [the qualification plan](AUTONOMOUS-TESTING.md).

A subsequent actual 0.4.4 Play-button test on LG/Retina Off reproduced the startup
timeout. The new failure label and policy restoration were visibly verified;
Exit Windows Steam and Quit Manager completed. A silent-launch candidate also
failed. Both Steam engine thread samples point into Core Audio device setup,
which is now the next investigation; Retina On is not a required trigger. The
earlier passing cycles remain valid lifecycle observations, not a hang fix.


## 0.4.5 WinMM startup fix — 2026-10-16

The repeated startup stall was isolated to legacy WinMM audio enumeration, not
Retina On: it also failed on the LG, original WinMM failed a standalone 45-second
watchdog, and an upstream four-patch candidate enumerated in about 0.6 seconds.
Both Windows architectures passed 23 silent playback formats, mixer closure and
invalid-format rejection. Two separate candidate builds were byte-identical;
the final integrated recipe also produced all four DLLs matching reviewed hashes.
The existing exit-only DLL bytes are unchanged. No Steam audio muting, renderer
replacement, synchronization override or host display change is installed.

Five candidate cold cycles passed (two LG, three built-in), followed by actual
packaged manager Play/Exit/Steam Exit/Quit on built-in Retina and a packaged LG
cycle. All restored `auto` and closed normally without orphan-overlay recovery.
A process memory map confirmed the candidate WinMM loaded in Steam. Prepared
outputs were 3024×1964 built-in / 2560×1440 LG; these remain distinct from current
visual/input acceptance. The LG target was restored at the end.

The 0.4.5 preview bundles both the current overlay and verified exit-only rollback.
Fresh packaged qualification passes install/repeat/legacy upgrade/explicit
rollback/opt-out, FFmpeg and uncached official Xcode discovery. Python regression
coverage is 219 tests. Native AppKit lifecycle tests remain passing. The original
engine and v1 payload are retained; an explicit rollback is preserved by setup.
The [startup investigation](STARTUP-INVESTIGATION.md) links private per-run evidence.

Game/Steam windows remain unavailable to the computer-use service. Their current
screenshots, pointer/focus checks, audible audio and gameplay performance are not
qualified. The actual manager Play view was inspected visually; offscreen fixture
renders cover other views without claiming a complete interactive walkthrough.
The menu telemetry capture includes startup/focus gaps and is not a gameplay
benchmark. Keep Steam's desktop interface as default; Big Picture is an optional
UX experiment, not a demonstrated performance optimization.
