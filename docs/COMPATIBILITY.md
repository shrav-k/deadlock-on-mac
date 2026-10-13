# Compatibility ledger

Keep observed results distinct from upstream claims. Last updated 2026-10-13.

| Configuration | Installation | Steam account | Deadlock rendering | Multiplayer / Cloud |
| --- | --- | --- | --- | --- |
| M2 Max, 32 GiB, macOS 26.6.2; Highball Wine 20261006 + DXMT a444716 | Steam and Deadlock build 25841406 installed | User confirmed successful sign-in | D3D11 probe passes; first game launch crashed | Not yet tested |
| Same Mac; Wine Sikarugir 11.0_1 + DXMT 0.80 | Steam installs and self-updates | Login UI stays black, including software rendering | D3D11 probe passes; game not tested | Not tested |
| Same Mac; official CrossOver 26.3.0 | App signature and notarization verified; trial opens | Not yet tested | Not yet tested | Not yet tested |

Manager: 26 automated tests pass locally on Python 3.13.2. These are not game
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
was stopped at the user's request before consolidation. No successful gameplay is
claimed. Cold restart after consolidation still needs testing.

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

For each live result add: date, macOS/chip/RAM, engine and graphics versions,
Deadlock build ID, resolution/settings, test duration, what worked, what failed,
and whether the test was observed directly or reported by another user. Do not
include account IDs, passwords, tokens, full local paths or unredacted logs.
