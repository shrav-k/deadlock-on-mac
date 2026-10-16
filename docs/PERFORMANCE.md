# Controlled performance tests

For current external-display research and hotdesking acceptance, see
[EXTERNAL-DISPLAYS.md](EXTERNAL-DISPLAYS.md). Detect each desk's monitor before
applying a saved laptop resolution; the connected monitor is not necessarily the
primary display or the game's target.

Start with one working runtime, AC power, Low Power Mode off, and a repeatable Hero
Sandbox route. `doctor` reports power status without changing system settings.
Keep Steam online under your existing account. Avoid runtime downloads/builds or
other heavy work during the measured segment.

Exit Windows Steam and all Wine apps before changing the launch environment:

```sh
python3 bin/deadlock-mac performance --fps-cap 60 --hud on --hud-log on
python3 bin/deadlock-mac steam
python3 bin/deadlock-mac launch
```

Settings live outside Git in `DeadlockData/performance/<profile>.json`. The cap
uses the paired DXMT build's `d3d11.preferredMaxFrameRate`. It is a requested limit;
confirm actual behavior with the HUD. Steam passes its startup environment to the
game, so sending a second launch request does not change an already-running client's
settings. The private **Steam startup log** normally receives the game's HUD output.

Also set the game's own limits after its first run, with Steam/Wine closed:

```sh
python3 bin/deadlock-mac game-fps --cap 60 --menu-cap 60          # preview
python3 bin/deadlock-mac game-fps --cap 60 --menu-cap 60 --apply  # backup and apply
```

The app has a separate **Set game and menu limits to 60 FPS** button. This changes
only `fps_max` and `fps_max_ui` in the single account's `machine_convars.vcfg`,
preserving unrelated settings and line endings. Unknown formats/duplicate keys
are refused. The original file and change receipt are kept under
`DeadlockData/settings-backups/`. Verify both limits in the game after restarting;
a saved cap is a ceiling, not a guarantee of minimum performance. We observed
400/120 in the saved game settings while the manager was requesting a 60 FPS
renderer limit, so the renderer request alone must not be reported as a verified cap.

`--sync auto` preserves the engine default. It does not mean synchronization is off.
`none`, `msync` and `esync` are explicit comparison options, requiring a full restart;
no one mode is claimed to improve every game or engine. `performance --reset` removes
these overrides on the next restart. Normal shader caches are preserved.

## Display and quality

Reach the menu using the normal Steam launch before changing display settings.
Choose a mode actually offered by the display and record the window
mode, refresh rate, quality, upscaler and render scale. The tested built-in Wine
mode list did not offer exact 1920×1080; a substituted 1920×1200 is not a 1080p pass.
Output resolution alone does
not establish native rendering resolution. Our initial fresh-install baseline was
1512×982 borderless with a saved render scale of approximately 73%, not native 1080p.

The optional `graphics-preset --mode borderless --width WIDTH --height HEIGHT`
command previews a narrow display edit (also accepts `--mode fullscreen`);
`--apply` requires Steam/Wine closed and backs up the original configuration first.
It supports only the tested video schema and a single account's configuration.
It preserves quality/render scale and is not a complete graphics-quality preset.
Prefer the in-game menu when investigating display-mode failures.

### Experimental high-resolution borderless / Retina

On the tested built-in M2 Max display, Wine's default desktop is 1512×982.
Enabling its Retina setting exposes a 3024×1964 desktop without changing the
macOS desktop scale. Borderless can use that desktop size while internal rendering
resolution is controlled separately by the game's upscaler/render scale. It does
not make arbitrary borderless output dimensions equivalent to desktop resolution,
and native output alone does not prove native internal rendering or steady 60 FPS.

With Windows Steam and all Wine apps closed:

```sh
python3 bin/deadlock-mac retina                    # saved setting only
python3 bin/deadlock-mac retina --set on           # preview
python3 bin/deadlock-mac retina --set on --apply    # apply; returns backup ID
# Example for this display only; choose the current display's actual dimensions:
python3 bin/deadlock-mac graphics-preset --mode borderless --width 3024 --height 1964 --apply
python3 bin/deadlock-mac launch
```

The app exposes Retina status/enable/disable under Display settings. This is
opt-in and experimental. The user confirmed visible coverage, pointer alignment,
Command–Tab, HUD output of 3024×1964, Game Mode On and both FPS limits at 60 after
a full Steam restart. In-game Exit Game also closed normally and Game Mode
restored, although the manager's earlier Exit request timed out. Gameplay testing
at this resolution was paused before the Mina ability comparison; sustained
performance and repeated lifecycle acceptance remain open. It affects the whole Wine bottle,
including Steam, and takes effect on restart. It does not change macOS preferences.
For CrossOver, use its own Retina control.

Only `RetinaMode` in Wine's version-2 user registry is edited. An atomic update
preserves other keys, rejects unknown/duplicate settings and refuses live Wine or
a changed registry. Backups contain that one setting, not Steam account data.
With Steam/Wine closed, `retina --restore BACKUP_ID --apply` restores its previous
value; `retina --set default --apply` removes the override. Video configuration
backups are separate under `DeadlockData/settings-backups/`. Disabling Retina also
requires selecting a resolution appropriate for the non-Retina desktop.

## Measure gameplay separately

Record when Hero Sandbox starts, warm up by moving/shooting/using abilities, then
repeat the same route for a measured segment. Ten minutes is a useful initial
warm-up allowance based on upstream player reports, not a guarantee that all shader
compilation is finished. Record focus changes and loading screens separately.

Use the native PID of **deadlock.exe**, not Steam or the short-lived launch-request
process. Analyze its private Steam log, for example:

```sh
python3 bin/deadlock-mac performance-report \
  --log '/path/to/private/steam-startup.log' --pid 12345 \
  --start-time '2026-10-13T12:30:00' --warmup-seconds 600 \
  --end-time '2026-10-13T12:45:00'
```

Times are local, matching the HUD log. Without `--start-time`, warm-up is measured
from that process's first valid HUD record, which may include menus. Reports exclude
other processes and duplicate identical records, and reject missing/malformed data.
They summarize presentation intervals and GPU times. Repeated interval pairs can
appear in Metal's output, so sample counts are **not unique game frames**, and the
report does not claim simulation FPS or conventional 1% lows. Time filters select
records; a record's samples can extend slightly before its timestamp. Loading or
focus-loss gaps are retained, not silently filtered as outliers.

Compare the same route after changing only one setting. A menu at 60 FPS does not
establish sandbox or match performance. Record crashes and visual/input/audio defects
alongside frame pacing. Raw logs may contain private Steam data; keep them out of Git.

The first M2 Max sandbox run did not sustain the target during Mina's ultimate
(summoning bats): the user saw 40 FPS or less. Use that same ability sequence for
the next comparison. Test fullscreen at the same resolution/quality before adding
1080p; 1920×1080 has about 40% more output pixels than 1512×982. The screenshot showed
Game Mode off. Apple Game Mode requires supported macOS fullscreen behavior; a
Windows fullscreen setting under Wine does not establish that it activated.
Confirm in the HUD/menu rather than assuming a performance or temperature benefit.
See [Apple's Game Mode requirements](https://support.apple.com/en-mide/105118).

Fullscreen can minimize when focus moves to another application: the tested game
configuration enabled `setting.fullscreen_min_on_focus_loss`. A minimized window
is not evidence of a crash. Match any Wine error report to the current Windows
process ID; a debugger from a prior exit can remain visible after another game
launch. Loading/minimization gaps also make whole-session average FPS misleading.

## Optional Game Mode diagnostic

On the tested M2 Max, macOS classified the Wine game as an anonymous process,
Command–Esc did not open Apple's Game Overlay, and the Metal HUD showed Game Mode
off even after selecting fullscreen in Deadlock. An Apple-signed `gamepolicyctl`
compatible with macOS 26 enabled Game Mode; both its status and the in-game HUD
confirmed it. The user then reported Mina's ultimate staying around 60 FPS with
the earlier stutter gone. This is a useful short sandbox result, not a sustained
match benchmark or proof that a Wine process receives every per-game priority.

The CLI automatically discovers and validates a compatible Apple tool:

```sh
python3 bin/deadlock-mac game-mode
python3 bin/deadlock-mac game-mode --prepare
```

Play enables a background Game Mode session by default; see the
[installation guide](INSTALL.md#automatic-game-mode-during-play). It saves the
original policy, enables before requesting Steam launch, follows only game
processes inside the selected bottle, and restores on actual exit. Closing the
manager or CLI does not end this watcher. There is no gameplay deadline; the
three-minute startup timeout only covers a game that never starts. The explicit
`launch --without-game-mode` path does not require this tool or Xcode. An older tool can
fail before execution on a newer macOS: Xcode 15's tool failed to load a GamePolicy
symbol on our macOS 26 machine. Setup skips incompatible copies, checks other
installed Xcode bundles and caches a verified tool for Play/recovery. If none
works, install/update Xcode from Apple. An explicit `--tool` override is also
supported. The manager
checks Apple's code signature and tool identifier before executing it, rejects
unknown status formats, and neither downloads nor distributes Apple's binary.

For a separate timed comparison, start Deadlock through Steam with automatic
Game Mode disabled and let the manager
identify the one running game:

```sh
python3 bin/deadlock-mac game-mode --test --seconds 300
```

Advanced comparisons can supply `--test-pid 12345` instead. The app preview has
equivalent tool selection, status, five-minute test, stop and recovery controls.

This changes a **system-wide policy**, not an individual game's preference. Start
only with automatic policy and run one test at a time. The command stays running
and restores automatic policy when the PID exits/changes, the timer expires, or
it receives Ctrl-C, SIGTERM or SIGHUP. The limit is 15 minutes. Keep the renderer,
resolution and quality unchanged; confirm Game Mode in the HUD and repeat the same
ability sequence. This is deliberately separate from normal Play and does not
modify Wine, Steam or game files.

Recovery is recorded before enabling in
`~/Library/Application Support/Deadlock Manager/GameMode/game-mode-test.json`.
Older workspace-local `DeadlockData/game-mode-test.json` receipts remain recoverable.
An uncatchable process kill, power loss, or Apple-service failure can prevent
automatic cleanup. After such an interruption, use:

```sh
python3 bin/deadlock-mac game-mode --restore
```

Supply the same compatible `--tool` path if needed. Restoration preserves a later
explicit `off` or `auto` choice; another actor setting `on` cannot be distinguished
from this test's override. A pending recovery blocks a new test. Do not infer
successful restoration from process exit alone—check the reported policy.

The new Play watcher uses Apple's system-wide override. For macOS to recognize
the Wine game and activate Game Mode natively, the remaining work is Wine app identity and
native fullscreen integration. Adding game metadata only to the manager's UI does
not establish that the Steam-launched child game becomes eligible. See
[Apple's game identification guidance](https://developer.apple.com/forums/thread/739387)
and [Game Mode adoption](https://developer.apple.com/videos/play/wwdc2025/209/).

Keep **Direct3D 11 with DXMT** for this comparison. It already renders through
Metal on the Apple GPU; Game Mode is separate from GPU acceleration. Vulkan is a
different backend requiring its own validated Wine/MoltenVK setup and measurements.
No Vulkan comparison has been performed here.

Sources: [paired DXMT configuration](https://github.com/gauthierpiarrette/dxmt/blob/a44471614f7cf4817e4eee717993eb19e35184b9/dxmt.conf),
[Apple Metal HUD](https://developer.apple.com/documentation/xcode/monitoring-your-metal-apps-graphics-performance),
[upstream Deadlock reports](https://github.com/gauthierpiarrette/highball-db/blob/main/db/games/deadlock.json).
