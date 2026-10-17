# LG image quality and performance comparison

The test display is a secondary LG at 2560×1440, 144 Hz over HDMI. Leave the Mac's
main display unchanged. Record the detected topology for every desk: a different
monitor invalidates saved dimensions. Start with the qualified Highball/DXMT pair,
Game Mode On during Play, game/menu caps 60, extra DXMT cap 0, and the Deadlock Steam
overlay disabled for the freeze investigation. Do not change these mid-run.

## Fixed game settings; no upscaling

The user requires **no upscaling** and wants the current Low graphics settings
preserved. Do not enable FSR, MetalFX, DLSS, reduced render scale or dynamic
resolution as a performance workaround. Record the existing configuration and
inspect it; if an existing upscale mode is found, flag the conflict before changing
it. Runtime comparisons must hold the game's configuration and workload fixed.

Capture Steam, the game menu and settings first. Verify monitor, actual output,
Game Mode and visual correctness. Check the same private sandbox scene for missing
geometry, corrupt textures and motion artifacts. The previous run's saved viewport
scale changed from 40% to 75% when the user changed quality; those mixed settings
make that run unsuitable for an image-quality A/B comparison.

## Resolution matrix

First qualify the capture/input path and runtime improvements at the existing LG
output. Only then compare actual game output resolutions, preserving the Low
quality settings. Do not implement a lower internal resolution disguised as the
same output resolution.

| Comparison | Output | Required validation |
| --- | --- | --- |
| Baseline | 2560×1440 borderless | Correct LG placement and unchanged game settings |
| Lower output | 1920×1080 windowed, if offered | Native 1:1 window, coverage, input, lifecycle |
| Lower output fallback | 1600×900 windowed, if offered | Native 1:1 window, coverage, input, lifecycle |
| Fullscreen qualification | Offered output mode only | Coverage, pointer alignment, Command–Tab and desktop restoration |

Borderless normally uses the desktop output. Setting a saved width does not prove
that a different output mode took effect. Verify PNG dimensions, HUD and settings
together. Fullscreen has prior cropping/focus failures; qualify it before measuring.
Lower resolutions must not be stretched/upscaled to fill the 1440p desktop. Do not
silently change the host display mode or main-display assignment to make a test pass.

## Wine and DXMT experiments after the visual baseline

- Frame pacing: use the game cap first. [DXMT's Metal pacing option](https://github.com/3Shain/dxmt/blob/main/docs/CUSTOMIZATION.md)
  requires a refresh-rate divisor. A separate reversible 120 Hz host-display trial
  may compare renderer cap 60 against game cap 60; 144 Hz + renderer cap 60 is not
  the default because we observed 48 FPS cadence.
- Synchronization: compare engine default, MSync and ESync with complete Steam
  restarts. [CodeWeavers](https://support.codeweavers.com/advanced-settings-in-crossover-mac-26)
  describes MSync improvements as application-dependent, not universal. Record the
  effective mode and repeat noisy results before choosing a default.
- Graphics: keep D3D11→DXMT as the baseline. DXMT, D3DMetal and DXVK are distinct
  backends; switching the game's API to Vulkan is another experiment, not an
  automatic upgrade. Qualify dependencies and smoke tests in a separate profile
  before touching the working installation. Never mix arbitrary runtime DLLs.
- Retina: apply according to the target's backing scale. CodeWeavers documents
  that high-resolution mode changes pixel doubling/DPI and can expose app bugs.
  A scale-1 LG does not need a forced laptop Retina configuration.
- CPU/GPU work: profile the fixed scene with Instruments before changing thread or
  scheduling behavior. Separate GPU execution time, CPU submission, synchronization
  waits and first-use shader compilation. Do not infer a bottleneck from temperature
  or FPS alone. Avoid generic thread-count/priority tweaks without a reproducible
  benefit and clean-exit regression checks.
- Upstream updates: compare matched Wine/DXMT builds in isolated profiles. Preserve
  the working runtime and shader caches, and qualify Steam, startup, input, rendering,
  exit and Game Mode restoration before performance measurements. A newer version
  number alone is not a reason to promote it.

For each candidate, follow [QUALITY.md](QUALITY.md): warm the same private sandbox
route, mark idle/effects/movement segments, run three A/B pairs with equal cooldown,
record frame intervals/GPU time and visual faults, and retain failed results.
Capture outside timed segments. Keep shader caches; annotate first-use compilation.
Use a later user-played match for endurance, not a controlled A/B comparison.
No runtime is promoted on a menu FPS number or version number alone.

## Upstream review, 2026-10-17

[Wine 11.20](https://github.com/wine-mirror/wine/blob/wine-11.20/ANNOUNCE.md)
is available as a development release. Its changes include WineMetalSwapChain
autorelease pools, a mac driver uninitialized-variable fix and DirectInput cleanup
waiting changes. These are candidates for compatibility/lifecycle review; the
announcement does not establish a Deadlock FPS improvement. Its WineD3D queue
optimizations also do not automatically benefit this D3D11→DXMT configuration.
Compare the exact Highball base and local patches before rebasing; qualify a
separate runtime first and keep the current LG setup recoverable.

The installed Xcode provides Metal System Trace, Game Performance and Time Profiler.
Use a short process-attached recording of the same sandbox scene, outside screenshot
capture and build activity. Follow [Apple's Metal performance analysis](https://developer.apple.com/documentation/xcode/analyzing-the-performance-of-your-metal-app)
to separate GPU work from CPU submission and synchronization. Profiling overhead
must be recorded; follow any proposed change with an uninstrumented A/B test.
