# Controlled performance tests

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

`--sync auto` preserves the engine default. It does not mean synchronization is off.
`none`, `msync` and `esync` are explicit comparison options, requiring a full restart;
no one mode is claimed to improve every game or engine. `performance --reset` removes
these overrides on the next restart. Normal shader caches are preserved.

## Display and quality

Reach the menu using the normal Steam launch before changing display settings.
For the 1080p comparison, choose custom 1920×1080 in the game and record the window
mode, refresh rate, quality, upscaler and render scale. Output resolution alone does
not establish native rendering resolution. Our initial fresh-install baseline was
1512×982 borderless with a saved render scale of approximately 73%, not native 1080p.

The optional `graphics-preset` command previews a narrow 1080p fullscreen edit;
`--apply` requires Steam/Wine closed and backs up the original configuration first.
It supports only the tested video schema and a single account's configuration.
It preserves quality/render scale and is not a complete graphics-quality preset.
Prefer the in-game menu when investigating display-mode failures.

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

Sources: [paired DXMT configuration](https://github.com/gauthierpiarrette/dxmt/blob/a44471614f7cf4817e4eee717993eb19e35184b9/dxmt.conf),
[Apple Metal HUD](https://developer.apple.com/documentation/xcode/monitoring-your-metal-apps-graphics-performance),
[upstream Deadlock reports](https://github.com/gauthierpiarrette/highball-db/blob/main/db/games/deadlock.json).
