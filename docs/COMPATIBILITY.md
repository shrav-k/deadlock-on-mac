# Compatibility ledger

Keep observed results distinct from upstream claims. Last updated 2026-10-13.

| Configuration | Installation | Steam account | Deadlock rendering | Multiplayer / Cloud |
| --- | --- | --- | --- | --- |
| M2 Max, 32 GiB, macOS 26.6.2; Highball Wine 20261006 + DXMT a444716 | Steam installs and self-updates; Deadlock downloading | User confirmed successful sign-in | D3D11 probe passes; game not yet tested | Not yet tested |
| Same Mac; Wine Sikarugir 11.0_1 + DXMT 0.80 | Steam installs and self-updates | Login UI stays black, including software rendering | D3D11 probe passes; game not tested | Not tested |
| Same Mac; official CrossOver 26.3.0 | App signature and notarization verified; trial opens | Not yet tested | Not yet tested | Not yet tested |

Manager: 23 automated tests pass locally on Python 3.13.2. These are not game
compatibility tests. The CrossOver trial started 2026-10-13; no purchase was made.

Both free-runtime probes reported Apple M2 Max, feature level 11.0, successful
device/swapchain creation, and 120 successful Present calls. This establishes API
operation, not visually verified game output. The Steam client updated itself to
build 1788652215. Highball login was confirmed by the user; this session's macOS
UI tool cannot enumerate the Wine windows. Account credentials were not inspected.

For each live result add: date, macOS/chip/RAM, engine and graphics versions,
Deadlock build ID, resolution/settings, test duration, what worked, what failed,
and whether the test was observed directly or reported by another user. Do not
include account IDs, passwords, tokens, full local paths or unredacted logs.
