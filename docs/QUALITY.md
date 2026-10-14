# Runtime qualification and performance protocol

The objective is a maintained Deadlock distribution with reusable runtime,
installation, lifecycle and measurement components. Other Windows games are a
future compatibility target; they are not supported merely because Steam opens.
Game IDs, process matching, config schema, saves and acceptance scenarios are
currently Deadlock-specific. Extract a game descriptor when a second title has a
real test case; keep authentication, Wine and renderer adapters separate.

## Evidence required before promoting a runtime

| Layer | Required evidence | Current automation |
| --- | --- | --- |
| Manager | Safe extraction/downloads, state isolation, rollback, lifecycle/recovery, telemetry filtering | Python unit suite on macOS/Linux, Python 3.12/3.13; Swift type-check and quit-policy tests |
| Build/provenance | Pinned source/toolchain/patches, ABI, hashes, licenses | Reviewed sechost overlay recipe; full engine reproduction still open |
| Windows APIs | Valid/invalid device handles in 32/64-bit, correct errors, no unhandled fault | Native notification probes |
| Rendering | Hardware adapter, D3D11 device/swapchain, repeated present | Native 120-frame probe; not a shader correctness suite |
| Steam | Fresh install, update, login/Guard, library, download, cold/warm restart | Valve UI acceptance plus opt-in `check_lifecycle.py --steam-only` idle/shutdown checks |
| Lifecycle | Ten normal quit/relaunch cycles, five manager Exit cycles, no debugger, exact Game Mode restoration | Automated watcher/exit logic and opt-in menu-only `check_lifecycle.py`; live results recorded separately |
| Input/display/audio | Mouse capture, keyboard/controller, focus, minimize, window modes, display scaling, audio/voice | Manual matrix; fullscreen regression currently open |
| Persistence | Supported Cloud sync verified in Steam, local backup and restore drill | Backup unit tests; full live restore drill open |
| Performance | Controlled repeated sandbox sequence plus full-match observation | Marked Metal HUD capture and frame-time statistics |
| Soak | A complete match, 60-minute session, memory trend, reconnect, clean exit | Pending user gameplay; no automated public matchmaking |

For broader Wine qualification, add Wine's own relevant `user32`, `sechost`,
`kernel32` and graphics tests and a pinned image-comparison rendering suite. The
small probes here do not replace the Wine conformance suite. Test supported Macs
and macOS versions individually; CI's unit tests cannot establish GPU behavior.
Do not run untrusted game binaries, inject into protected games, disable updaters,
or silently accept a different renderer when a candidate fails.

## Candidate lanes

Keep working, candidate and rollback artifacts separate and immutable. The default
is the best-tested **complete stack**, not whichever component has the largest
version number. Record Wine base version, source commit/patchset, renderer build,
macOS/SDK, game and Steam builds, settings and known failures together.

As checked on 2026-10-13, upstream has
[Wine 11.19 development source](https://github.com/wine-mirror/wine/blob/wine-11.19/ANNOUNCE.md).
The newest available package in the selected
[macOS build channel is 11.18](https://github.com/Gcenx/macOS_Wine_builds/releases/tag/11.18).
It passes both notification probes in a fresh isolated prefix here. It has **not**
passed current Steam, DXMT integration or Deadlock gameplay; it is not the default.
Highball's published 2026-10-06 build reports Wine 11.0 and includes macOS patches
needed by its paired DXMT. Rebase those patches and qualify the whole stack before
promoting 11.19 or a later release. Never transplant arbitrary DLLs across them.

Use `packaging/check_runtime.py --wine /absolute/path/to/wine` with the same
`--workspace` and `--compiler-bin` options to initialize a disposable prefix and
run both API probes. Add `--graphics` only to test that candidate's own graphics
stack; a passing result does not imply DXMT is loaded. Private artifacts go under
`Tools/runtime-checks/`. No Steam credentials or full game installation is copied.
The harness stops only the candidate prefix it created.

A hotfix should include a minimal reproducer, before/after results, source/license
provenance, both architectures, rollback and live acceptance. Keep upstream patch
attribution. Retire a backport when the qualified base incorporates it. Prepare an
upstream report or PR from this evidence; submitting it is a separate maintainer
action. These two exit patches already exist upstream.

## Performance experiments

1. Plug in; disable Low Power Mode; allow the Mac to cool. Record display/refresh,
   resolution, render scale, quality, FPS cap, renderer, actual Game Mode state,
   game build and cache condition. Do not change them mid-comparison.
2. Run one warm-up pass. Record cold-cache behavior separately; do not delete the
   working player's shader cache to manufacture a cold run.
3. Use the same Hero Sandbox camera position, hero and target group. Record
   30 seconds idle, repeat Mina's bat ultimate in a fixed sequence, then move/fire
   for 60 seconds. Mark each stage. Compare at least three warm A/B pairs, reverse
   their order, and give the Mac the same cooldown. Use a replay only if supported
   by the game; never automate input in a public match.
4. Compare mean presentation rate, p95/p99/p99.9 interval, slowest 1% mean interval,
   worst interval, and counts over 16.67/33.33/50/100 ms. Retain loading/focus gaps
   in the complete report and publish explicitly marked gameplay segments too.
   HUD intervals are not unique simulation frames; do not call them true 1% FPS lows.
5. Predeclare acceptance: no startup/exit regressions, no new visual/input faults,
   and no repeatable >5% worsening of p99 versus the working baseline. That 5%
   threshold is a proposed project rule, not an established hardware guarantee.
   Investigate noisy results and report every repetition, including failures.
6. Observe a full user-played match. This tests real workload and thermal endurance,
   but two unrelated matches are not a controlled A/B benchmark. Report network
   problems separately from render stalls.

## Record the later match

Enable logging with Steam closed once, then use normal Play with Game Mode:

```sh
python3 bin/deadlock-mac performance --fps-cap 60 --hud on --hud-log on
python3 bin/deadlock-mac launch --game-mode-tool /absolute/path/to/gamepolicyctl
# Once gameplay starts; retain the returned run ID:
python3 bin/deadlock-mac benchmark start --scenario manual-match --resolution '1920x1200; verify display mode'
python3 bin/deadlock-mac benchmark mark --run RUN_ID --label gameplay
python3 bin/deadlock-mac benchmark mark --run RUN_ID --label team-fight
python3 bin/deadlock-mac benchmark finish --run RUN_ID
```

The recorder locates the running game's actual output file (including stderr), even when Steam was
opened earlier. It restricts reads to private manager logs, tracks the inode and
initial offset, filters by PID/time, and refuses rotated/truncated logs or empty
samples. Start only after the desired gameplay window begins. Finish works after
the game exits. Reports live in `DeadlockData/benchmarks/`; raw Steam logs stay
private. Free-text labels should contain no player/account information.

Power and Game Mode are sampled at start/end, not continuously. Current capture
does not measure temperature, GPU utilization or input latency. Use Instruments
Metal System Trace/Time Profiler for an explicit diagnostic recording if those
questions remain; do not infer CPU/GPU bottlenecks or throttling from heat alone.

## Fullscreen/display matrix

Fullscreen and high-resolution borderless are separate qualification targets.
The user prioritized high-resolution borderless after the fullscreen coverage and
focus failures; a borderless pass must not be reported as a fullscreen fix. For each
advertised resolution, separately test cold startup, in-game change from a smaller
and larger mode, focus away/back, pointer hit-testing at all screen edges, clean
quit, relaunch and restoration of the desktop. Record requested and actual output
sizes plus display identity without serial numbers. Test built-in and external
displays separately, then primary-display changes, mixed refresh rates and
connect/disconnect recovery when that hardware is available.

External-display use is the primary target for the next user gameplay session.
Record connection type, macOS primary display, scaling, refresh, requested/output
dimensions and internal render scale. Include lid-open/lid-closed use where
applicable, explicitly launching on an external secondary display without changing
the macOS primary display, Command–Tab, quit/relaunch,
and unplug/reconnect recovery. These are pending hardware acceptance checks;
the built-in-display Retina result does not qualify an external display. The
manager defaults its display editor to borderless with empty dimensions, so it
cannot silently apply this laptop's resolution to a different monitor.

`tests/native/fullscreen_probe.c` exercises DXGI mode matching, fullscreen state,
resize, presentation, client/window/desktop geometry and restore. It creates only
its own test window. A successful HRESULT is insufficient: geometry must match
and visible coverage still requires observation. An unsupported requested mode
must not silently become a passing test of a different mode. A hung test is a
failure; keep its log and restore the desktop before proceeding.

Compile it with the pinned LLVM-MinGW toolchain, linking `d3d11`, `dxgi`,
`dxguid` and `user32`. Run it with the selected profile's complete environment
(including DXMT and any reviewed overlay), after closing Deadlock. First run
`fullscreen-probe.exe --list-modes`, then pass an explicit sequence such as
`fullscreen-probe.exe 1512x982 1920x1200 1800x1125 1512x982`, using only dimensions
actually enumerated for that display. The probe fails if exact mode matching,
geometry or desktop-resolution/refresh restoration fails. Listing modes does not
change display mode. The current probe targets the display containing its initial
window at (100, 100); selecting a non-primary external display is still future
work, not implied by a pass on the built-in display.

The initial built-in-display probe accepted 1512×982 and 1920×1200 but matched
1920×1080 to 1920×1200, which was recorded as unsupported rather than passed.
These were API/geometry results only. The real game's fullscreen cold launch,
pointer alignment, focus recovery and clean exit remain separate acceptance steps.

### Display inventory is not visible-output verification

`tests/native/display_inventory_probe.c` queries Win32, DXGI and an explicitly
supplied SDL3 library. Compile with the pinned LLVM-MinGW toolchain using
`-Wall -Wextra -Werror -O2 -municode`, linking `dxgi`, `dxguid` and `user32`.
Pass the installed game's absolute Windows path to `SDL3.dll` as its sole argument
and use the complete selected runtime environment. The probe creates no window
and changes no display mode. A zero exit status means inventory collection
succeeded; it does not verify where a game appears or its drawable resolution.

`tests/native/macos_display_inventory.swift` supplies a separate native host
reference via AppKit/CoreGraphics. Compile with `xcrun swiftc` and run it without
arguments. It collects names, current logical/backing dimensions, scale, primary
status and session-only IDs; it collects no serials and performs no UI actions.
Guest API agreement is not independent physical-pixel evidence: all guest paths
can share the same Wine driver assumptions. Compare with host metadata, then
visible own-window and game acceptance. See [WINE-PRACTICES.md](WINE-PRACTICES.md).

## Distribution gate

Release a versioned, notarized app with verified runtime pins, bundled installer
runtime, license notices/corresponding source, clear storage requirements and a
rollback path. Test fresh installation, interruption/resume, low disk, offline
failure, paths with spaces, and upgrades preserving the existing Steam library.
Full engine/dependency reproducibility, license inventory, public binary release,
notarization and this acceptance matrix remain open. Do not label the current local
preview "works out of the box" until those gates pass on a clean Mac.
