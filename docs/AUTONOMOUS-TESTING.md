# Autonomous qualification and optimization

Plan established 2026-10-16. The user has resumed live testing and authorized
launching/closing the manager, Windows Steam and Deadlock on either connected
display. Use the existing signed-in installation. Public matches, parties,
invites and account prompts remain user-operated. Private Hero Sandbox may be
operated through observed UI; never send blind input or infer a visible pass from
a running process.

## Session controls

- Capture a baseline before edits: git commit/dirty state, manager version,
  macOS/Xcode, runtime/renderer/hotfix hashes, game build, power, Game Mode policy,
  host display topology, Wine scaling, video settings and FPS caps. Keep account
  files and raw logs in private `DeadlockData` folders, outside Git.
- Use one profile and one game instance at a time. Back up changed settings and
  retain the existing shader cache. Avoid duplicate game downloads.
- Hold a temporary `caffeinate -diu -t 14400` assertion during an attended agent
  test session; release it at completion or interruption. Four hours is an idle
  recovery bound, not a limit on normal play. Do not change password requirements
  or permanent sleep settings. A manual lock still requires the user to unlock.
- Keep AC power and Low Power Mode off for comparisons. Check available thermal
  pressure signals and allow cooldown between workloads. `pmset` reporting no
  warning is not a temperature measurement or proof of no throttling.
- Stop a failing case before trying another variant. Preserve logs, attempt
  normal game/Steam shutdown, and verify Game Mode restoration. A hung process,
  missing UI access, topology change or failed recovery blocks dependent tests;
  do not report skipped checks as passes.
- Pause input immediately if the user takes over. Do not automate public
  matchmaking or send social messages. No process injection or anti-cheat changes.

## Ordered gates

| Gate | Work that can run autonomously | Evidence required to advance |
| --- | --- | --- |
| 1. Dependencies | Fresh packaged FFmpeg/Game Mode preparation; Python suite; native AppKit tests | New official Xcode source/hash, no prior cache, unchanged policy, compiler and tests pass |
| 2. Baseline and recovery | Record host/profile state, back up settings, verify current processes and recovery receipts | No game/watcher left active; sufficient disk; expected displays and power |
| 3. Actual manager UI | Open canonical app; Settings/Diagnostics; idle Quit/Command–Q; close during a cancellable grid and Steam exit | UI observations plus child-process completion and saved cleanup result |
| 4. Owned display probes | Prepare each named display; popup and SDL desktop presentation; repeated start/stop | Geometry, actual screenshot, all four edges, logged corner clicks, focus away/back, menu-bar behavior, unchanged host layout |
| 5. Game menu | Launch through manager and Steam; verify selected display, output/HUD, pointer and focus; normal Exit; Steam Exit | Visible game/menu, correct output, Game Mode On, actual exits and exact original policy restored |
| 6. Controlled sandbox | Navigate observed UI into private Hero Sandbox; fixed camera/hero sequence; mark idle/effects/movement segments | Correct scene and actions, warmed repeated runs, enough PID-filtered HUD samples, no input/display/exit regression |
| 7. Candidate optimization | Change one variable, warm up, run A/B then B/A, repeat three times | Better pacing beyond run-to-run noise with acceptable image quality; lifecycle gates still pass |
| 8. Endurance | 30–60 minute private workload with periodic health checks; user-played full match later | Memory/frame-time trend, stable session, cloud sync observation, clean exit and relaunch |

Gate 1 passed for Xcode 27.1 / macOS 26.6.2; see [Game Mode setup](GAME-MODE-SETUP.md).
The other gates require current-session evidence. A CLI check does not qualify an
actual manager button, and a desktop grid does not qualify the game.

## Display matrix

Keep the built-in screen as the macOS main display. Select the LG by name/UUID
through the manager. Prepare only while Windows Steam is closed. Automatic
Retina is On for the built-in 2× display and Off for the LG 1× display. It is a
bottle-wide Wine setting; re-prepare and restart between targets.

| Target | First baseline | Subsequent cases |
| --- | --- | --- |
| Built-in | 3024×1964 borderless output, Retina On, existing FSR2 scale, 60 FPS caps, Game Mode On | Compare lower internal render scales; Retina Off is a separate diagnostic case |
| LG ULTRAGEAR secondary | 2560×1440 borderless output, Retina Off, existing quality, 60 FPS caps, Game Mode On | Compare render scale/quality; 120 Hz versus current 144 Hz only as an explicit, reversible host-mode experiment |
| Fullscreen | Owned SDL-desktop and DXGI probes first | Revisit game fullscreen only after coverage/focus/restore gates; no claim that borderless repairs exclusive fullscreen |
| Hotdesking | Validate saved target and reject stale mappings | Disconnect/reconnect, other monitors, lid state and cable changes require the physical hardware/user; never simulate these as completed |

Record logical desktop coordinates, current backing pixels, guest/client size,
actual HUD output and internal render scale separately. A high resolution in a
dropdown is not proof of the drawable size. Require an actual screenshot and
input evidence where computer use supports the Wine window. If it cannot access
that window, finish API/lifecycle checks independently and request only the
missing visual or interaction evidence.

## Optimization order

1. Preserve DXMT/D3D11, the exit hotfix, 60 FPS limits and automatic Game Mode as
   the working baseline. Verify actual loaded renderer and policy each run.
2. Measure current external-display pacing before modifying settings. Separate
   menu samples from gameplay. Capture Mina's bat ultimate only after navigating
   to and verifying that hero/ability in the current game build.
3. Compare internal render scale, then shadow/effects/post-processing settings
   individually. Keep output resolution, refresh, camera, scene and power fixed.
4. Investigate refresh cadence, presentation and synchronization only after a
   repeatable baseline. Do not promise that Game Mode or fullscreen fixes every
   bottleneck. Use supported Instruments captures for unresolved CPU/GPU stalls.
5. Evaluate newer Wine/DXMT or an official CrossOver comparison as complete,
   pinned candidate stacks in isolated small test prefixes first. No arbitrary
   DLL mixing, Steam updater freezing or promotion on version number alone.
6. For a runtime fix: minimal reproducer, relevant Wine tests, both architectures,
   provenance, before/after data, rollback and game acceptance. Prepare upstream
   patches/reports; publication requires a separate explicit instruction.

Compare mean presentation rate, p95/p99/p99.9 intervals, slowest 1% mean interval
and stall counts. HUD samples are presentation intervals, not unique game frames;
do not label them true 1% FPS lows. Use at least three warmed paired runs and
report all failures. Adopt a candidate only if the improvement exceeds observed
variance and it introduces no lifecycle/input regressions. An unrelated public
match is an endurance observation, not a controlled A/B benchmark.

## Execution and records

Use existing `check_onboarding.py`, `check_manager_app.py`, `check_lifecycle.py`,
display probes and benchmark CLI before adding new harnesses. Add tests only for
new behavior or a demonstrated regression. Every case records start/end, requested
settings, evidence paths, result (`pass`, `fail`, `blocked`, `not-run`), limitations
and recovery outcome under `DeadlockData/qualification/`.

The agent works through runnable gates in the active conversation and reports
concrete blockers. It does not promise background iteration after the turn ends;
scheduled continuation requires an explicit automation. At completion, stop
test-owned processes, verify restored Game Mode and desktop topology, release the
keep-awake assertion, and leave one canonical manager app with the selected
working configuration. Preserve private failure evidence for the next run.

Related protocols: [quality gates](QUALITY.md), [performance](PERFORMANCE.md),
[external displays](EXTERNAL-DISPLAYS.md), [Wine practices](WINE-PRACTICES.md).
The [GitHub project review](GITHUB-RESEARCH.md) records pinned upstream leads,
license boundaries and the next experiments, rather than treating recipes as proof.

## UI images and repeatable workloads

Run `python3 packaging/check_manager_snapshots.py --output <new-private-folder>`
for 16 synthetic manager views: waiting/failure Play, Settings and Diagnostics,
two content widths and light/dark appearances. This renders our own views offscreen;
it does not capture the desktop or start Wine. Retain the manifest and source
revision, review PNGs for clipping/contrast, and compare only equivalent OS/font/
scale fixtures. A successful render is not an approved visual baseline. Actual
sidebar navigation, scrolling, focus and buttons still need the native app checks
and a computer-use walkthrough.

For Steam/game screenshot checks, capture through an available, observed UI
surface. Keep account/friends content private. Record display ID, backing pixels,
game build, presentation mode, scene, sample time and pass/fail/block reason.
Check window bounds and known menu/HUD anchors; mask changing clocks, player
names and animations before a reviewed image comparison. Pixel equality across
different monitors or game builds is not an acceptance criterion. If the tool
cannot address the Wine window, mark that gate blocked instead of replacing it
with a process check or unobserved clicks.

For autonomous performance work, use three distinct workloads:

1. **Startup/menu:** cold/warm launch time, process-specific rendering samples,
   normal exit, exact Game Mode restoration and complete Steam/Wine shutdown.
   This is the currently runnable lifecycle lane; menu metrics are not gameplay.
2. **Private sandbox:** observed navigation, known hero/ability, fixed camera and
   timed idle/effect/movement markers; run warmed A/B and B/A repetitions. Stop
   on loss of observable focus, a dialog, scene mismatch or thermal pressure.
3. **Local replay candidate:** a user-owned, build-compatible demo and fixed
   camera/tick range may provide a repeatable workload without matchmaking.
   Validate playback on the actual build through Steam first. No suitable local
   demo was found in this installation on Oct 16; no replay command was executed.
   Do not assume Source/CS2 `timedemo` commands work in current Deadlock. Replay
   playback does not measure live networking/input or replace a user-played match.

Keep median/p95/p99 presentation intervals, stall counts, memory and power/thermal
context alongside images; require the same scene and adequate sample counts.
Do not optimize based on menu-only 60 FPS readings. Existing `benchmark` commands
already support PID-filtered logging and timestamped scene markers.

Steam fullscreen is a separate UX candidate. Valve describes
[Big Picture](https://store.steampowered.com/bigpicture/) as a TV/controller interface;
it is not evidence of faster Deadlock rendering. Keep the current desktop client
default. Qualify optional Big Picture on both displays, focus recovery and exit
before exposing it as a launcher preference, without altering the game profile.

Current startup findings and outstanding uncertainty are recorded in
[the Retina investigation](STARTUP-INVESTIGATION.md).
