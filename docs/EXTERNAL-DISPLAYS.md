# External displays, runtime research and performance plan

Research checked **2026-10-14**. Recommendations below are experiments, not measured
FPS gains. Use [COMPATIBILITY.md](COMPATIBILITY.md) for actual local results and
[QUALITY.md](QUALITY.md) for promotion gates. Steam remains responsible for the
account, game installation, updates and online play in every runtime comparison.

## Current evidence and the hotdesking requirement

The connected LG UltraGear reports **2560×1440 at 144 Hz**, non-mirrored, while the
built-in screen remains primary (1512×982 logical desktop, 3024×1964 pixels at
120 Hz). The user confirms HDMI and intends to use many different displays.
Exact model, HDR/VRR capability and normal lid state are not established. AC power
and Low Power Mode off were confirmed. No external gameplay benchmark has run.

The previously tested 3024×1964 borderless configuration passed laptop coverage,
input and focus checks. It must not be applied blindly to a new monitor. At native output,
1440p has 3.69 million pixels: about 38% fewer than that laptop Retina output, but
78% more than 1920×1080. These are pixel counts, not predicted FPS. Internal render
scale, particles, CPU work and the compositor also matter.

For the first external baseline, select the intended monitor before launching,
verify its actual output in the HUD, and use **2560×1440 borderless, DX11/DXMT,
Game Mode On, game/menu caps 60**. Preserve the existing quality/upscaler settings
for the initial comparison and record them. Do not describe this as native
internal rendering unless render scale is verified. Validate coverage, pointer
alignment, Command–Tab, manager Exit and desktop restoration before gameplay.

**Later investigation:** the user wants monitor selection without changing the
macOS primary display. Win32, DXGI and the game's SDL3 enumerate the secondary LG,
but Retina mode makes them report it as 5120×2880 while native macOS reports
2560×1440 at 1×. The current saved game file is 2880×1800 borderless with monitor
index 1; it was left unchanged. Do not apply the proposed baseline until output
selection and scaling are qualified. [Wine/CodeWeavers review](WINE-PRACTICES.md)
contains the isolated comparison, source limitations and manager-picker design.
Making the external screen primary is an optional workaround, not a requirement.

Hotdesking acceptance must cover:

| Situation | Required behavior / evidence |
| --- | --- |
| New display before Play | Enumerate current displays/modes; choose target explicitly; never reuse an absent monitor index or stale dimensions |
| Mixed Retina and ordinary displays | Record logical desktop, backing pixels and game drawable separately; pointer alignment at all edges |
| HDMI, USB-C/DisplayPort, dock | Record connection and advertised modes; no assumed VRR, HDR or bandwidth from the monitor name |
| Primary-display or lid change | Re-enumerate; verify the launch target and saved output; repeat focus and quit tests |
| Disconnect/reconnect | Test at the menu first; recover to a connected screen without trapping input, leaving black space or losing Game Mode restoration |
| 1080p, 1440p, 4K, ultrawide desks | Use modes actually enumerated; keep aspect ratio; distinguish output from internal render resolution |
| Runtime upgrade | Repeat this matrix; a menu rendering correctly is not display qualification |

The manager currently reports displays and offers reversible manual settings. It
does **not** yet automatically migrate game settings across monitors. A future
display policy should prefer the selected connected screen, remember optional
per-display choices locally, and fall back visibly when a screen is absent. Do
not publish display serials. Re-enumerate immediately before applying a choice;
never rewrite video files while Steam/Wine is running. Keep backups and an explicit
preview of changes. Auto-detection should not silently change global macOS settings.

## Presentation, refresh rate and Game Mode

For the HDMI desk, test fixed **120 Hz with the 60 FPS cap**, if offered, against
the current 144 Hz. Sixty divides 120 evenly; it does not divide 144. This is a
pacing hypothesis, not a guaranteed stutter fix. The pinned DXMT config explicitly
recommends a preferred frame rate that divides the display refresh and warns that
Core Animation may deliver a different rate. Verify the observed cadence rather
than trusting the requested limit. [Pinned DXMT configuration](https://github.com/gauthierpiarrette/dxmt/blob/a44471614f7cf4817e4eee717993eb19e35184b9/dxmt.conf)

On a compatible future desk, test VRR separately. Apple's documented Adaptive Sync
path uses Thunderbolt/USB-C/DisplayPort and says to avoid HDMI cables/adapters.
Only count VRR as enabled if macOS offers and selects Variable/Adaptive for that
connection. Ordinary 144 Hz output does not prove VRR. There is no need to buy a
cable before completing the fixed-refresh baseline. [Apple Adaptive Sync](https://support.apple.com/en-us/102144)

Borderless and exclusive fullscreen are different tests. Apple's direct-to-display
path depends on the native window, opaque Metal layer and system conditions; use
the HUD's Direct/Composited field to observe it. A Windows fullscreen checkbox
does not prove native macOS fullscreen or direct presentation. The runtime owns
the game's window, so changing the manager window cannot repair it. [Apple window guidance](https://developer.apple.com/documentation/metal/managing-your-game-window-for-metal-in-macos)

Keep automatic Game Mode enabled for the baseline: it produced the clearest local
improvement so far, with the user reporting Mina's bat ultimate near 60 FPS and
stutter gone in the earlier test. That was not a sustained external-display result.
Apple describes CPU/GPU scheduling priority and reduced background interference;
this is separate from GPU acceleration. Our watcher uses a verified Apple tool's
system-wide policy override, not native per-game eligibility, and restores the
prior setting after the actual game exits. [Apple Game Mode](https://support.apple.com/en-us/105118)

## Runtime and emulator findings

The current pipeline is Windows game APIs through Wine, x86 CPU execution through
Rosetta, and D3D11 graphics through DXMT to Metal on the Apple GPU. Wine provides
Windows compatibility; a full Windows VM is a different architecture. Replacing
one component with its newest version does not qualify the complete stack.

| Option | Verified research finding | Decision for this project |
| --- | --- | --- |
| Installed Highball Wine 11.0 + DXMT `a444716` + reviewed exit overlay | Local Steam/account, menu, GPU rendering and repeated lifecycle evidence | Preserve as the rollback baseline |
| New Highball Wine build `20261014T003801Z` | Adds spatial audio/channel handling and registry-backed app package APIs; r25 still pins the same DXMT artifact | Candidate for broader compatibility; no demonstrated Deadlock FPS gain |
| Upstream Wine 11.19 / packaged macOS Wine 11.18 | Newer source and binary channels exist; our 11.18 API probes pass, Steam/DXMT/Deadlock do not yet have acceptance | Qualify the entire macOS stack before promotion |
| Updated/rebuilt DXMT | A specific resolution-change deadlock fix is missing from the installed source | Highest-priority targeted display investigation |
| Game's native Vulkan renderer + Wine Vulkan + MoltenVK | Separate graphics path, with a Vulkan portability subset and feature limitations | Optional controlled comparison after display/lifecycle stability |
| D3D11 + DXVK + MoltenVK | Adds a D3D-to-Vulkan translation path; current upstream DXVK is not automatically compatible with every MoltenVK build | Use only a reviewed, paired candidate; never assume it is faster |
| Official CrossOver / D3DMetal | Optional alternative provider; Apple's current GPTK page advertises evaluation and profiling tooling | Retain optional support; not the unpaid open-source foundation |
| Native ARM64 Wine + FEX | Highball has an active development line with source-based CPU fidelity tests | Strategic durability lane, not a drop-in upgrade |
| Windows ARM VM | Parallels and UTM use guest Windows plus x86 translation and a virtual GPU path | Secondary research lane; no Deadlock performance claim |
| Asahi Linux + FEX/Proton | Separate operating system with a native Apple GPU Vulkan driver | Interesting long-term comparison, poor immediate fit for macOS hotdesking |

### Specific patches and version discipline

Wine's current announcement is **11.19**, including a Wine startup-delay fix but
no promise of faster Deadlock. Gcenx's newest selected macOS release is **11.18**.
The installed Highball engine derives from CrossOver's published Wine source and
has additional macOS/renderer patches. A Wine version number alone omits this
compatibility work. [Wine 11.19](https://github.com/wine-mirror/wine/blob/wine-11.19/ANNOUNCE.md),
[macOS 11.18 package](https://github.com/Gcenx/macOS_Wine_builds/releases/tag/11.18)

The newer Highball engine release was published at 2026-10-14 00:40 UTC. Its three
new Intel-line patches concern spatial audio and app packages; the earlier Retina
HORZRES/VERTRES correction is already in our October 6 build. Upgrading this Wine
artifact alone therefore does not add a new Retina fix. Its r25 manifest still
uses DXMT `a444716`. [Engine patch series](https://github.com/gauthierpiarrette/highball-engine/blob/e13247c012/patches/README.md),
[r25 manifest](https://github.com/gauthierpiarrette/highball/blob/main/spike/engines/x64-crossover26.3-r25.json)

Upstream DXMT commit **`e94c312f5c054263acf261cfa109edf13e757587`** releases the
swapchain mutex before `resizeWindow` in the windowed `ResizeTarget` path. Direct
inspection confirms our pinned source lacks that line. It is a plausible hang
candidate, not proof of our previous crash/cropping cause. First reproduce a
reentrant resize in a small DXGI test, then build baseline versus that backport
with identical Highball integration. Check cold launch, resize, focus and exit on
both displays before real gameplay. [Upstream fix](https://github.com/3Shain/dxmt/commit/e94c312f5c054263acf261cfa109edf13e757587)

Do not replace the pinned renderer with an arbitrary branch named `main`: the
Highball fork's main branch and our pinned branch have diverged. The renderer
depends on the matching Wine Metal glue. The pinned configuration also offers
`dxgi.handleAltTab`; it warrants an isolated fullscreen focus test, not an assumed
fix for cropping. Rebuilding DXMT requires LLVM 15 and a suitable Xcode Metal
toolchain. The installed Xcode 15 is below upstream's Xcode 16+ prerequisite;
current CLT compilation of our manager does not satisfy that renderer build need.
[DXMT build/debug guide](https://github.com/3Shain/dxmt/blob/186a2327f1ec76376f6bc1ef64636f08b0728567/docs/DEVELOPMENT.md)

### Durability beyond Rosetta

Apple now states that general Rosetta support is available through macOS 27;
macOS 28 restricts it to certain older, unmaintained games. We cannot assume this
actively updated Wine/Deadlock stack qualifies. A durable free project needs a
tested alternative CPU execution path, not just archived Intel Wine binaries.
[Apple's Rosetta support statement](https://support.apple.com/en-us/102527)

Highball's native line currently combines Wine 11.18 ARM64X/ARM64EC, patched FEX
2610, Vulkan renderers and patched MoltenVK. Its README says it is not yet offered
to players, requires its signed Wine loader with Apple's cross-architecture
entitlement, and does not currently use DXMT. Reported compute-loop results on
other Macs are not Deadlock benchmarks. Qualification must include entitlement
and distribution feasibility, 32/64-bit Steam helpers, CPU/exception fidelity,
graphics correctness and local M2 Max acceptance. Never treat ad-hoc signing as
a substitute for a required entitlement. [Native engine design](https://github.com/gauthierpiarrette/highball-engine#the-arm64-line),
[pinned inputs](https://github.com/gauthierpiarrette/highball-engine/blob/main/inputs-arm64.json)

MoltenVK 1.4.2 is the current release reviewed here. It maps a Vulkan subset to
Metal; API-version claims are not a guarantee that a game's needed extensions
or shader semantics work on M2. Test native Vulkan separately from DXVK, capture
the loaded driver and actual adapter, and check visual correctness as well as
timing. [MoltenVK](https://github.com/KhronosGroup/MoltenVK),
[release 1.4.2](https://github.com/KhronosGroup/MoltenVK/releases/tag/v1.4.2)

UTM research needs current sources: the old statement that Windows guests have no
3D acceleration is outdated. UTM 5 prereleases introduce experimental Windows
DirectX support through Triton/Neptune. However, 5.0.6 explicitly warns that its
Windows 3D driver requires an unreleased update and directs affected users to the
previous version. This is not a ready replacement for our baseline. A Windows VM
also consumes additional disk and requires its own Windows setup/licensing; none
was installed. [UTM 5.0.6 release](https://github.com/utmapp/UTM/releases/tag/v5.0.6),
[Triton architecture](https://blog.getutm.app/2026/introducing-triton-directx-11-driver-for-qemu/)

Parallels documents DirectX support through 11.1; that establishes a supported API
range, not Deadlock acceptance or faster performance, and it is a commercial
option. [Parallels gaming guidance](https://kb.parallels.com/en/122485)

Asahi combines FEX, Wine/Proton and native Vulkan, avoiding macOS Metal translation.
Its current M2 matrix still marks Thunderbolt and DisplayPort Alt Mode work in
progress and describes HDMI audio caveats. Dual boot, storage and dock support
make this a separate project rather than our next experiment.
[Asahi gaming architecture](https://asahilinux.org/2024/10/aaa-gaming-on-asahi-linux/),
[M2 support matrix](https://asahilinux.org/docs/platform/feature-support/m2/)

## Ranked performance experiments

1. **Validate display and pacing.** Establish the correct monitor/output, 60/60
   caps, Game Mode and clean lifecycle. Compare fixed 120 versus 144 Hz if offered.
   Test VSync independently; its latency/tearing tradeoff must be observed. Keep
   HDR state constant and record it. Do not introduce HDR and VRR together.
2. **Separate CPU stalls from GPU cost.** Compare the same Mina sequence at two
   internal render scales while output stays fixed. Falling GPU time with rising
   frame rate suggests graphics pressure; unchanged frame time suggests another
   limit, but requires a trace to attribute it. A frame rate ceiling of 60 cannot
   reveal spare throughput by itself.
3. **Tune image quality deliberately.** Compare FSR2 1.5× with the next offered
   scale before reducing monitor output. At 2560×1440, a standard 1.5× scale means
   roughly 1707×960 input; actual game behavior must be verified. Compare particle
   clarity, moving silhouettes and ghosting. FSR2 reconstructs from lower-resolution
   data and has its own cost; it is not free performance. Then change shadows,
   fog/AO or effects one at a time if GPU evidence justifies it.
   [AMD FSR2 documentation](https://gpuopen.com/manuals/fidelityfx_sdk/techniques/super-resolution-temporal/)
4. **Keep shader caches and measure warm-up.** Preserve the player's working
   cache. Record first-use ability stalls separately from warm repetitions. DXMT
   documents cache controls; disabling or clearing caches is a diagnostic, not a
   routine optimization. Do not enable Metal validation/debug layers during FPS
   comparisons. Compare a final HUD-off run to estimate capture overhead.
5. **Compare synchronization only after a baseline.** Test the manager's `auto`,
   `msync` and `esync` modes with a full Steam/Wine restart and an unchanged render
   configuration. Confirm the actual active path. The installed Highball patchset
   already contains an msync registration-leak fix; “enable msync” is not a new
   universal cure. Report memory growth and frame pacing, not just average FPS.
6. **Measure sustained power/thermal behavior.** Keep AC power and Low Power Mode
   off. High Power Mode is an optional comparison only if this Mac actually offers
   it; the current `pmset` capability output did not advertise a high-power control.
   Apple's documentation describes increased cooling/fan speed, not a guaranteed
   game gain. Keep ventilation and cooldown consistent; heat alone does not prove
   throttling. [Apple power modes](https://support.apple.com/en-us/101613)
7. **Compare reviewed runtime candidates.** Prioritize the targeted DXMT display
   fix, then newer complete Wine/renderer combinations. Native Vulkan and ARM64/FEX
   are later lanes. Keep immutable artifacts and rollback receipts; no replacement
   of a live prefix, blanket DLL transplantation or automatic latest-version promotion.

Do not stack unmeasured registry “VRAM” changes, vendor-ID spoofing, process priority
tweaks, cache deletion and renderer switches. They obscure causes. Frame generation
is also not evidence of a faster simulation or lower input latency; it is not a
proposed baseline change for this competitive game.

## Measurement tools and test suite

Use our PID/time-filtered capture for repeatable summaries, with its documented
limits: HUD log intervals are not unique simulation frames, so the existing parser
does not provide conventional game-frame 1% lows. Mark idle, ability, movement,
loading and focus transitions separately. The 60 FPS budget is 16.67 ms; 120 FPS
would require 8.33 ms. Target 60 first and record p95/p99 intervals, long stalls,
GPU time and correctness across at least three warm A/B pairs with reversed order.

Apple's current HUD offers timed performance reports, shader compilation tables
and CPU/GPU frame information, with `MTL_HUD_REPORT_URL` controlling the destination.
Investigate this as a separate capture adapter; its report statistics must not be
conflated with our existing log parser. [Apple HUD reports](https://developer.apple.com/documentation/xcode/generating-performance-reports-with-metal-performance-hud)

HUD insights can flag serial compilation, encoder switching and CPU encoding
pressure (`MTL_HUD_INSIGHTS_ENABLED=1`). Some additional insights are specific to
GPTK's D3D12 evaluation environment and do not automatically apply to our DX11
stack. Treat them as profiling hints, not automatic fixes.
[Apple performance insights](https://developer.apple.com/documentation/xcode/gaining-performance-insights-with-metal-performance-hud)

For attribution, use a short Instruments Metal System Trace/Time Profiler recording
of a repeatable local sandbox sequence. Current GPTK tooling also exposes newer
profiling workflows, but the selected local Xcode lacks `metalperftrace`; `xctrace`
exists in the older installation. Install a compatible developer toolchain when
needed for a renderer build or trace—not as a player prerequisite or an FPS tweak.
[Apple Game Porting Toolkit](https://developer.apple.com/games/game-porting-toolkit/)

Expand tests in layers: manager units and native AppKit integration; Wine API
conformance and our notification probes; a reentrant-resize regression and
multi-output DXGI geometry tests; a pinned shader/image correctness suite; cold/warm
Steam lifecycle; actual display/focus/audio checks; repeated sandbox workloads;
then a user-played full match and a sustained session. A shader microbenchmark
cannot replace the real match, and unrelated matches are not controlled A/B runs.
Report network stalls separately. No automated matchmaking or game-input injection
is part of this plan.

Keep candidate prefixes small for probes. Sharing the live Steam account prefix
between simultaneous runtimes is not a safe storage shortcut. Avoid duplicate
game downloads; decide on an isolated library/backup strategy before a candidate
needs full Steam acceptance. Publish compact redacted reports and build provenance,
not raw Steam logs, credentials, proprietary game files or full trace archives.
