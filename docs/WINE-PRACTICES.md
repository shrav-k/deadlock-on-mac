# Wine and CodeWeavers practices: evidence and implementation decisions

Implementation follow-up: the 0.3.0 manager now includes the named display picker
and guarded preparation described here. See [current setup and acceptance status](EXTERNAL-DISPLAYS.md).

Reviewed **2026-10-14**. This review uses CodeWeavers support documentation,
upstream API specifications, the matched local Wine source, and isolated probes.
It is not an endorsement or a claim of equivalent CrossOver compatibility.
Community tips hosted on codeweavers.com are not official support guidance.

## What to adopt from CrossOver

| Practice | Source evidence | Project decision |
| --- | --- | --- |
| Application-specific installation recipes | CrossOver's Steam recipe chooses the bottle, dependencies and installer, then lets Steam update and authenticate | Keep Steam as the owner of installation/account/update state; describe the complete tested runtime and dependency set in a versioned recipe |
| Application-specific graphics choices | CrossOver 26's Auto mode consults its own per-game database; an explicit backend applies across the bottle | Maintain our own evidence-backed Deadlock recipe. Do not interpret Auto as the fastest backend, or assume our default reproduces CodeWeavers' database |
| Reversible environments | CodeWeavers recommends bottle archives before modifying settings and warns that version changes can make bottles incompatible with older releases | Isolate candidate prefixes; retain exact setting backups for narrow edits. A settings backup is not a complete prefix rollback |
| Bounded issue reproduction | Their debug workflow records the failing action and then closes the program and compresses the log | Separate diagnostic runs from performance runs; preserve exceptions and process order, cap retention and keep account data private |
| Explicit recovery | CrossOver distinguishes ordinary Quit from Force Quit | Keep successful shutdown, timeout and explicit recovery as separate results. Do not automatically label a force-stop as a clean exit |

Sources: [Steam installation](https://support.codeweavers.com/installing-steam-in-crossover?kb_language=en_US),
[CrossOver 26 settings](https://support.codeweavers.com/en_US/advanced-settings-in-crossover-mac-26),
[Mac user guide](https://support.codeweavers.com/en_US/user-guides/crossover-mac-user-guide),
[version isolation](https://support.codeweavers.com/installation-issues/install-and-use-multiple-versions-of-crossover-on-mac),
[debug logging](https://support.codeweavers.com/troubleshooting/creating-a-debug-log).

CodeWeavers documents installation detection, preferred bottle templates,
dependency relationships and Steam IDs as separate recipe concepts. These are
useful design precedents for a modular manager. Our implementation should define
its own schema and recipes, rather than distribute their proprietary database.
[CrossTie application profiles](https://support.codeweavers.com/en_US/crosstie-data-startpage/c4-data-application-profile)

For dependencies, prefer a reproducible minimal set established by logs and
installation tests. CodeWeavers also offers a broad dependency archive for
troubleshooting, while explicitly noting that success with it does not identify
which dependency mattered. That shortcut is unsuitable as evidence for this
project's lean default. The unresolved Intel FFmpeg imports in our engine still
need a real media-path test and a supported packaging resolution.
[Troubleshooting dependencies](https://support.codeweavers.com/troubleshooting-unlisted-applications-cxmac)

Keep prefixes on a local filesystem with the required links and permissions.
CodeWeavers advises against network-backed bottle locations. Our repository,
downloads, runtime artifacts, account-bearing prefix and private diagnostics
remain separate; distributing the repository must never distribute a signed-in
Steam prefix. [Storage guidance](https://support.codeweavers.com/en_US/advanced-crossover-mac-configuration)

## Secondary displays do not inherently need to be primary

Windows supports selecting and positioning on a particular monitor. Primary-screen
metrics are not a substitute for that monitor's bounds, and negative coordinates
are valid. This matters here: the LG is above and to the right of the laptop's
origin. [Microsoft monitor positioning](https://learn.microsoft.com/en-us/windows/win32/gdi/positioning-objects-on-multiple-display-monitors),
[virtual screen coordinates](https://learn.microsoft.com/en-us/windows/win32/gdi/the-virtual-screen)

The installed Deadlock configuration contains `setting.monitor_index`, and both
current renderer DLLs refer to it. Inspection of the installed `tier0.dll` monitor
helpers shows bounds-checked, zero-based access to SDL's display list. That is a
candidate configuration path, not proof that every launch mode honors the saved
value. The initial file contained index 1, 2880×1800 borderless and a saved viewport
scale of 0.4. Those values were preserved during read-only investigation; they must not be described as the
previous laptop acceptance settings or verified live rendering settings.

### Window activation and Spaces

Our matched CrossOver-derived Wine source and upstream `cocoa_app.m` use
`WineAppWillActivateNotification` to ask other Wine applications in the same prefix
to yield activation. Since macOS 14 the receiving foreground app uses
`yieldActivation(to:)` followed by `activate(from:options:)` to handle a notification
race. The native manager originally did not participate. Version 0.3.1 implements
that handoff for a user-initiated launch with prefix, engine executable, foreground,
expiry and duplicate-PID guards. It does not repeatedly steal focus or move another
app's windows. [Wine source](https://github.com/wine-mirror/wine/blob/wine-11.0/dlls/winemac.drv/cocoa_app.m),
[Apple yield API](https://developer.apple.com/documentation/appkit/nsapplication/yieldactivation(to:)),
[Apple activate API](https://developer.apple.com/documentation/appkit/nsrunningapplication/activate(from:options:))

This is a candidate remedy, not proof of the LG failure's cause. On the first LG
attempt the user never saw a game window despite Metal rendering samples. Neither
Win32 activation nor a Metal drawable proves visibility in the active macOS Space.
Apple documents that a Space shows its own windows and that application switching
behavior is configurable. Do not change the user's global Spaces preferences as a
blanket workaround. Coordinate a manager-button test and record real coverage,
pointer alignment, Command–Tab and exit separately.
[Apple Spaces guide](https://support.apple.com/guide/mac-help/work-in-multiple-spaces-mh14112/mac)

SDL can enumerate displays and map each one to its Windows monitor handle. Its
instance IDs change after reconnect, so neither a transient ID nor a hardcoded
index is an adequate persisted hotdesking preference.
[SDL enumeration](https://wiki.libsdl.org/SDL3/SDL_GetDisplays),
[monitor handles](https://wiki.libsdl.org/SDL3/SDL_GetDisplayProperties),
[ID lifetime](https://wiki.libsdl.org/SDL3/SDL_DisplayID)

Old Valve guidance for Dota's Linux `-sdl_displayindex` flag is not sufficient
evidence that the current Windows Deadlock build accepts the same flag. Do not
add it to the default launch command without testing that exact build.
[Valve's Dota discussion](https://github.com/ValveSoftware/Dota-2/issues/13)

## Retina is a scaling policy, not a resolution unlock switch

CodeWeavers describes High Resolution Mode as changing pixel mapping and reporting
192 DPI, and notes application compatibility limits. Our setting currently edits
only Wine's `RetinaMode`; the installed registry DPI remains 96. These are not
equivalent configurations. Raising DPI blindly could affect Steam and every other
application in the bottle; it is not a demonstrated fix for Deadlock.
[High-resolution behavior](https://support.codeweavers.com/en_US/advanced-settings-in-crossover-mac-26),
[bottle DPI scope](https://support.codeweavers.com/reset-the-dpi-using-wine-configuration)

The local matched `winemac.drv/display.c` multiplies original-mode dimensions by
two when Retina mode is enabled. The probe reproduces this on the ordinary LG
as well as on the laptop. Windows API answers can also depend on the caller's DPI
awareness. The probe explicitly uses system-DPI awareness; it does not establish
Deadlock's own awareness or all per-monitor behavior.
[Wine display source](https://github.com/wine-mirror/wine/blob/wine-11.0/dlls/winemac.drv/display.c),
[Microsoft DPI virtualization](https://learn.microsoft.com/en-us/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows)

### Local read-only comparison

The native AppKit/CoreGraphics probe and `system_profiler` independently describe
the host. The Windows probe compares Win32, DXGI and **the installed game's SDL3
library** (version 3.5.0); it never launches Steam or Deadlock or creates a window.
The three guest APIs share Wine's driver, so agreement between them is not three
independent validations of physical pixels.

| Observation | Built-in | LG ULTRAGEAR, secondary |
| --- | --- | --- |
| Native macOS logical desktop | 1512×982 | 2560×1440 |
| Native backing pixels / scale | 3024×1964 / 2× | 2560×1440 / 1× |
| Highball, Retina enabled | 3024×1964 | 5120×2880 |
| Highball, Retina disabled | 1512×982 | 2560×1440 |
| Official signed CrossOver 26.3, fresh default Win10 64-bit bottle | 1512×982 | 2560×1440 |

All three guest enumeration paths identify the LG separately from the primary
display. The temporary Retina-off test restored the original setting and left
macOS layout unchanged. The CrossOver comparison used its normal wrapper and a
disposable bottle, with no copied Steam account or game installation; its default
graphics behavior was retained. It is not a controlled DXMT performance comparison
or a test of CrossOver's GUI High Resolution toggle. The temporary bottle was
removed after preserving the small diagnostic records.

The 5120×2880 guest mode is a **coordinate/reporting discrepancy to investigate**.
It does not prove a 5K Metal drawable, four times the GPU cost, or a scaling bug in
the actual game's presentation. No display placement or gameplay pass is claimed.
Private evidence: `DeadlockData/display-investigation/2026-10-14/`.

## Recommended manager display design

Offer a target picker: **System default**, **Prefer external display**, or a
specific currently connected screen. Preserve the user's macOS primary display.
For multiple external screens or ambiguous identical models, require an explicit
choice rather than guessing. Resolve the selection again before Play and after
reconnect; show a clear fallback if the selected display disappears.

Separate native display identity, macOS logical bounds, host backing pixels,
Wine bounds, SDL index, requested output and actual drawable. Never equate these
fields merely because their dimensions sometimes match. Store persistent identity
only locally; exclude serials and raw EDID from shared reports.

Use a backed-up game setting or verified Steam launch argument to select the
monitor. Starting with the game's own selector is preferable to moving another
application's window after launch. Manual borderless-window movement is a recovery
option, not a reconnect policy. Changing the system main display remains an
optional troubleshooting step, not a requirement of the manager.

Treat the high-DPI choice separately. A proposed external-display recipe may use
Retina off for a 1× monitor, but it must pass actual coverage, drawable-size, input,
focus and quit tests before becoming a default. Retina is currently bottle-wide:
if a change is needed, require a clean Wine/Steam restart and preserve user state.
Do not silently edit an active prefix or claim per-monitor DPI support we have
not implemented. The display picker is a design proposal, not shipped in 0.2.2.

## Performance and version discipline

CrossOver 26 uses Wine 11.0 plus its selected integrations; the latest upstream
development number is not by itself a compatibility ranking. Its release history
includes Steam fixes involving MSync, reinforcing the need to qualify launcher
lifecycle along with frame rate. [CodeWeavers release history](https://www.codeweavers.com/crossover/changelog)

Compare synchronization settings rather than universally enabling them. Our
`auto` currently supplies no override; the matched source's MSync implementation
requires `WINEMSYNC` to be set and nonzero. Capture the actual chosen environment
and restart the bottle between candidates. Do not infer MSync, a particular
renderer, or hardware acceleration from a UI toggle alone. CrossOver's newer
settings page differs from its older ESync/MSync guidance; recommendations must
be tied to the runtime version.

Keep DXMT as the working baseline while testing a precisely matched display fix.
Treat D3DMetal, DXVK/MoltenVK, Vulkan and newer Wine as separate complete-stack
experiments with rollback. CodeWeavers' DLSS/MetalFX feature is not automatically
provided by our free runtime. Optional official CrossOver comparisons use the
existing trial/license; no vendor bundle modification or component extraction is
needed to follow the engineering practices above.

## Tests that can establish the result

1. **Contract tests:** use the relevant pinned Wine `user32` monitor/DPI/window and
   `dxgi` tests; compare against a real Windows reference where available. Record
   expected failures and unsupported calls. Wine's own monitor tests can change
   modes/DPI, so inspect and isolate them before running the whole executable.
2. **Independent host checks:** collect native display bounds and backing scale
   before/after. Require no unintended primary-display, refresh or layout change.
3. **Own-window rendering checks:** create a test window on each selected display;
   draw a border, corner labels and pixel grid. Verify visible coverage and input
   coordinates, then inspect the Metal drawable separately from DXGI claims.
4. **Actual game menu:** launch through the signed-in Steam account onto a secondary
   display; verify selection, actual output, cursor alignment at all edges,
   Command–Tab and clean Exit/Game Mode restoration. Repeat with primary unchanged.
5. **Hotdesking:** test unplug/replug at the menu, negative origins, reordered
   screens, mixed scale, changed refresh, lid state and missing preferred display.
6. **Performance:** only after those gates, run the same warmed Mina sequence in
   repeated, order-reversed comparisons. Record output and internal render scale,
   loading/focus gaps, power, memory and frame pacing. The real match is a separate
   endurance observation; unrelated matches are not matched A/B experiments.

CodeWeavers' QA writing describes testing Windows API behavior across Windows and
Wine and investigating regressions; it is historical methodology, not a statement
about their current private CI coverage.
[CodeWeavers QA account](https://www.codeweavers.com/blog/caron%2Bretired/2015/10/2/how-im-earning-my-beer-part-1)
Current source tests are available in the pinned local Wine source and
[upstream monitor tests](https://github.com/wine-mirror/wine/blob/wine-11.0/dlls/user32/tests/monitor.c).
The WineHQ testing wiki/dashboard could not be fetched during this review, so
their current instructions/results have not been treated as reviewed evidence.

For commands and release gates see [QUALITY.md](QUALITY.md). This review adds
diagnostic evidence and a concrete design; it does not qualify external gameplay,
fix exclusive fullscreen, or establish a sustained 60 FPS result.
