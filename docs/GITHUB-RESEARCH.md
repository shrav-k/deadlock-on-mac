# macOS Wine and Steam project review

Checked 2026-10-16 using GitHub CLI repository metadata, README files, pinned
source files and CI workflows. No third-party setup scripts were executed.
Repository `updated_at` includes activity other than code changes, so maintenance
assessment uses archive status, source push date and inspected commit. Upstream
performance reports are leads, not local Deadlock qualification.

## Projects worth following

| Project / inspected revision | Useful findings | Application here |
| --- | --- | --- |
| [Highball](https://github.com/gauthierpiarrette/highball/tree/b2c1e0dd172bbd629eaf05586906d2dc7dabb4c4), source pushed Oct 15; GPL-3.0 | Native launcher plus CLI, separate recipe/database project, pinned engine manifests; CI runs upgrade and empty-home smoke checks and validates recipes | Closest architectural reference. Keep runtime, game recipe, measurements and UI independent; extend fresh/upgrade qualification instead of copying its UI wholesale |
| [highball-engine](https://github.com/gauthierpiarrette/highball-engine/tree/bd456bb21d442df8f9d23ddf986a4734d72be31c), Oct 16; LGPL-2.1-or-later | Pinned CrossOver Wine sources, attributed patch series, corresponding source, renderer/build separation; an explicitly experimental arm64/FEX line | Candidate engine build/provenance and conformance-test reference. Its experimental architecture is not a qualified replacement for our Rosetta stack |
| [highball-db](https://github.com/gauthierpiarrette/highball-db/tree/483aac4628cc7d3209299fe283c506de05c6eb4e), Oct 16 | Declarative recipes and provenance-labelled compatibility records | Strong starting schema reference for future game recipes. Curated data/recipes are CC0; derived predictions are ODbL, anti-cheat import has its own MIT notice |
| [frankea/Whisky](https://github.com/frankea/Whisky/tree/3abfbae945e3400caaa13cf2e78fe5a187a1405b), Oct 1; GPL-3.0 | Active community fork; distinct Steam orchestration, Wine environment, backend selection, diagnostics and test modules | Study launch coalescing, process tracking and renderer isolation. Retain our normal Steam shutdown path; its process-stop implementation is not equivalent |
| [Sikarugir](https://github.com/Sikarugir-App/Sikarugir/tree/c6e2bfa5548d8f3f21cda52409e13b4315461414), Oct 16 | Successor to Wineskin, paired wrapper/engine distribution and multiple renderer choices | Useful compatibility and packaging reference. It is not uniformly open source: README distinguishes LGPL components from launcher/creator components; inspect each license before reuse |
| [Merlot / macos-wine-steam](https://github.com/ByMedion/macos-wine-steam/tree/0ba12939f374ad4d3825e496551716bd09b1264d), Jun 25; MIT | Small Steam/DXMT setup and per-game launcher configuration; detached sessions, Retina/mouse options | Compare the minimal user workflow and recipe boundaries. Its documented Wine 11.10/DXMT 0.74 defaults are not current qualification evidence for our stack |
| [MacPlay](https://github.com/insourcewetrust/macplay/tree/5a8c74a918a8a322809809394f9812d2aeb80a67), Oct 2; MIT for its own code/data | Alpha Sikarugir frontend with hardware-aware advice, per-game engine choices and contextual reports | UI and data-model ideas. Do not import estimated FPS as measured results or adopt its quarantine-removal setup behavior |
| [DXMT upstream](https://github.com/3Shain/dxmt/tree/50102f994b406f58f56d5d09f2ad20f9b90390a2), Oct 16 | D3D10/11-to-Metal implementation and renderer configuration; current LICENSE says LGPL-2.1-or-later | Primary source for renderer behavior and candidate revisions. Keep our currently paired renderer pinned until tests pass; licenses can differ by revision |
| [Heroic](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/tree/509a34feea8541b73c928e289f2cf262d432db4a), Oct 15; GPL-3.0 | Mature multi-store frontend with runtime installation tests and separate backend/UI modules | Broader launcher design reference, not evidence that Deadlock works. Its GameMode setting is Linux-only Feral GameMode, not Apple's Game Mode |
| [Gcenx/macOS_Wine_builds](https://github.com/Gcenx/macOS_Wine_builds/tree/8022307824e05272af7427a02ed61774e925871a) | Upstream macOS package channel used by several wrappers | Candidate runtime source, not a guarantee that the newest package has the patches needed by our DXMT pair. Inspect release assets separately from source-branch activity |

The original [Whisky-App/Whisky](https://github.com/Whisky-App/Whisky) is archived;
its source was last pushed in May 2025. Its recent repository activity/star count
does not mean active maintenance. The community fork above is a separate project
with a separate distribution identity.

## Most relevant technical leads

### Retina metrics and fullscreen

Highball's engine carries an attributed Wine patch removing a second doubling of
`HORZRES`/`VERTRES` in Retina mode. The patch describes disagreement between GDI
caps, `GetSystemMetrics` and `EnumDisplaySettings`, and reports cropped fullscreen
in other games. This resembles our symptom but does not establish Deadlock's cause.
[Pinned patch](https://github.com/gauthierpiarrette/highball-engine/blob/bd456bb21d442df8f9d23ddf986a4734d72be31c/patches/0020-winemac-retina-horzres-not-doubled.patch)

Our `tests/native/display_caps_probe.c` now measures those APIs per display,
without creating a window or changing modes. Compile with the pinned LLVM-MinGW
compiler and `-Wall -Wextra -Werror -O2 -luser32 -lgdi32`; run through the complete
profile environment with Steam closed. Compare Retina Off and On against the
native host inventory. A mismatch warrants a minimal reproducer and isolated
candidate-engine comparison; a matching result is not a fullscreen visual pass.

Local result on the pinned Highball Wine build: **the extra GDI doubling did not
reproduce**. With Retina Off, the primary metrics/monitor/mode/GDI size were
1512×982 and the LG monitor/mode/GDI size was 2560×1440. With Retina On they were
3024×1964 and 5120×2880 respectively. Desktop caps reported the combined virtual
desktop, not the individual monitor. Host modes/topology did not change. The
second display doubling with Retina On reflects the bottle-wide policy already
documented here; it is distinct from an additional doubling in GDI caps. Do not
apply the cited patch as a demonstrated fix for our cropped fullscreen case.
Private logs: `DeadlockData/qualification/20261016-autonomous/retina-*-caps.log`.

Highball also implements per-executable `EmulateModeset` for games requesting modes
the host cannot switch to, together with the environment's mode-list builder.
Its code deliberately avoids making this a global default. Consider this only
after a matching failed-mode-change trace, with saved registry state and a
controlled probe. Do not blanket-apply it to Deadlock or all Steam games.
[Implementation and rationale](https://github.com/gauthierpiarrette/highball/blob/b2c1e0dd172bbd629eaf05586906d2dc7dabb4c4/Sources/HighballKit/DisplayModeEmulation.swift),
[tests](https://github.com/gauthierpiarrette/highball/blob/b2c1e0dd172bbd629eaf05586906d2dc7dabb4c4/Tests/HighballKitTests/DisplayModeEmulationTests.swift)

### Steam lifecycle and game-specific state

Highball explicitly checks whether a running Steam client has the renderer,
synchronization and other inherited settings requested by the next game. A second
launch command cannot retrofit the environment of an already-running client.
This is a useful invariant for our future per-game profiles: record a non-secret
launch receipt, reject mismatched settings while a game runs, and perform a normal
client restart before applying a new stack. Do not copy its reported CEF
workarounds without reproducing the matching failure here.
[Restart policy](https://github.com/gauthierpiarrette/highball/blob/b2c1e0dd172bbd629eaf05586906d2dc7dabb4c4/Sources/HighballKit/SteamRestart.swift)

The Whisky fork isolates Steam startup behind a driver and an orchestrator,
coalesces concurrent client startup and shares short-lived process snapshots.
Those are useful testability/performance patterns for a future multi-game manager.
Its stop method calls a process-kill driver, so that code must not replace our
Steam-owned normal exit/sync and Game Mode restoration behavior.
[SteamClientOrchestrator](https://github.com/frankea/Whisky/blob/3abfbae945e3400caaa13cf2e78fe5a187a1405b/WhiskyKit/Sources/WhiskyKit/Steam/SteamClientOrchestrator.swift)

Its display configuration concerns Wine virtual-desktop presets; that is distinct
from our named physical-monitor mapping and backing-pixel verification. A
"match display" preset or 1080p fallback does not solve mixed-DPI secondary
placement. [Display configuration](https://github.com/frankea/Whisky/blob/3abfbae945e3400caaa13cf2e78fe5a187a1405b/WhiskyKit/Sources/WhiskyKit/Whisky/BottleDisplayConfig.swift)

Our live 2026-10-16 test found a separate immediate-relaunch race after normal
Steam exit. Waiting for the selected server with `wineserver --wait` resolved
three repeated source-CLI cycles. This follows Wine's documented shutdown wait
and persistence behavior; it is independent of upstream UI recipes.
[Wine server semantics](https://github.com/wine-mirror/wine/blob/wine-11.0/server/wineserver.man.in)

### Frame pacing and Game Mode

DXMT documents its Metal/Core Animation coordinated limiter and recommends a
rate that divides the monitor refresh. Therefore the LG's 144 Hz versus a
supported 120 Hz mode at a 60 FPS cap is a useful controlled experiment, not an
automatic optimization. MetalFX spatial upscaling is another renderer-specific
candidate; compare it separately from the game's FSR2 and record output/internal
resolution. [Renderer configuration](https://github.com/3Shain/dxmt/blob/50102f994b406f58f56d5d09f2ad20f9b90390a2/dxmt.conf)

No inspected file established a lightweight, supported Apple Game Mode override
for this Steam/Wine chain. Heroic's similarly named option is explicitly Linux
only. Keep the verified Xcode-backed setup and its public/private-API distinction;
investigate native Wine host eligibility separately.
[Heroic GameMode source](https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/blob/509a34feea8541b73c928e289f2cf262d432db4a/src/frontend/screens/Settings/components/GameMode.tsx),
[our Apple setup findings](GAME-MODE-SETUP.md)

## Consolidation priorities

1. **Now:** reproduce display metrics, retain the verified restart fix, and make
   fresh setup plus upgrade/recovery gates part of every candidate qualification.
   Highball's CI is a useful example: it explicitly checks out recipe data so
   recipe tests do not silently skip. [CI](https://github.com/gauthierpiarrette/highball/blob/b2c1e0dd172bbd629eaf05586906d2dc7dabb4c4/.github/workflows/ci.yml)
2. **Next:** declarative game descriptors for app ID, process names, settings
   schema, supported renderers and test scenarios. Separate observed evidence,
   upstream reports and predictions. Preserve Steam ownership of accounts,
   downloads, social state and supported Cloud sync.
3. **Candidate lane:** reproducible Wine/renderer builds with corresponding
   source, small attributed patches, rollback and measured promotion criteria.
   Review Highball engine's fidelity probes before expanding our own conformance
   coverage. Do not promote its experimental arm64/FEX line on README benchmarks.
4. **Distribution:** signed/notarized release, upgrade smoke tests, inventory of
   component licenses and explicit optional proprietary dependencies. Reuse
   ideas freely; code/data incorporation requires the actual file/revision
   license and attribution. This review copied no upstream implementation code.

Do not blindly consolidate generic GPU spoofing, sandbox-disable variables,
estimated success percentages, anti-cheat claims or forced process-kill recipes.
Each change needs a current source, a matching local failure, a reversible test
and evidence of improvement. See [the execution plan](AUTONOMOUS-TESTING.md).
