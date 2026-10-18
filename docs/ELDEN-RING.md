# Elden Ring / Seamless Co-op research

Reviewed 2026-10-17. This is a requirements record, not a macOS compatibility pass.
The current working Deadlock prefix, DXMT build and configuration are preserved.

Follow-up: [free D3D12 qualification](D3D12-RESEARCH.md) records passing
Highball/D3DMetal 4.0b2 shader/readback/presentation probes, a reproducible ABI
failure in the tested VKD3D fork, exact package pins, and remaining game gates.
These results do not enable the Elden Ring research recipe's Play action.

## Rendering and runtime

Elden Ring is Steam app **1245620**. Its published Windows minimum specifies
DirectX 12 and 60 GB of storage; macOS is not listed as a supported platform.
[Steam requirements](https://store.steampowered.com/app/1245620/)

Our pinned DXMT stack implements Direct3D 10/11, so it cannot be reused as Elden
Ring's D3D12 backend. This is a capability gap, not a performance setting or a
reason to force a fictitious DX11 launch flag.
[DXMT upstream](https://github.com/3Shain/dxmt)

CodeWeavers documents D3DMetal support for DX11/12. An intact official CrossOver
provider is a comparison candidate; it is not proof that this game's mod stack
works. A durable unpaid D3D12 route still needs a separately licensed and qualified
provider/renderer design. Do not extract a commercial runtime or silently change
Deadlock's renderer to satisfy the second game.
[CodeWeavers graphics settings](https://support.codeweavers.com/advanced-settings-in-crossover-mac)

## Mod requirements

The author's current GitHub release is **Seamless Co-op 2.0.1**, published
2026-09-03; release notes name game version 1.17. Recheck upstream and the exact
installed game build before testing rather than treating the major version as a
permanent compatibility promise. The GitHub asset metadata reports SHA-256
`848ae27e1c77217590dac401c012a17d9b4f05b9b9a24aa33af54d8d7b8ba2a1` for
`Seamless.Co-op.v2.0.1.zip`. This is recorded provenance, not verification of a
locally downloaded or installed package.
[Author's release](https://github.com/yuiamoroll/EldenRingSeamlessCoopRelease/releases/tag/v2.0.1)

The author's installation/use instructions require an owned game, an online,
signed-in Steam session, matching game/mod versions among players and a shared
session password. Standalone installation uses `ersc_launcher.exe` and its
`SeamlessCoop` files, including locale data and `ersc_settings.ini`. No additional
mod is required for plain Seamless Co-op. The mod uses its own multiplayer route
and disables EAC; normal Steam Play is not interchangeable with that route.

The default mod save extension is `.co2`, separate from vanilla `.sl2`. Do not
convert modded saves back to vanilla. Treat Steam Cloud coverage of mod/custom
save extensions as unverified. The author prohibits modification/repackaging/
redistribution without permission, so launcher distribution should supply
metadata/instructions rather than bundle the mod.
[Author's description and FAQ](https://www.nexusmods.com/eldenring/mods/510)

For a combined randomizer campaign, the documented alternative launch route is
Mod Engine 2 with the Seamless DLL in `external_dlls`, file mods referenced by the
generated TOML, and a consistent save extension. Everyone needs the same relevant
mods. The standalone launcher must not silently replace that route or omit the
fixed world data. The community Seamless guide is useful setup evidence; its
older examples do not prove compatibility for our selected current builds.
[Seamless modding guide](https://ersc-docs.github.io/seamless-modding/)

Mod Engine's upstream describes the external launcher and configuration mechanism.
Its project being open source does not establish redistribution rights for every
mod or generated game asset in a campaign pack.
[Mod Engine 2 upstream](https://github.com/soulsmods/ModEngine2)

## Qualification order

1. Implement and verify a D3D12 provider in a separate profile. Reuse verified
   downloads where possible; do not copy the entire Steam library for experiments.
2. Verify Windows Steam login, installation detection, dependencies and clean
   shutdown; then the intended game route at its menu, without importing saves.
3. Verify the exact mod/component hashes, launch configuration and save namespace.
   Track the final `eldenring.exe` process, not just a launcher that exits early.
   Prove normal exit before enabling automatic Game Mode for this recipe.
4. Qualify the fixed private campaign pack separately: world hashes, explicit game
   path, profile-specific settings, safe save transfer and modded save isolation.
   Preserve existing Windows launchers and campaign data during the macOS port.
5. Repeat display coverage, pointer alignment, app switching, audio, Game Mode
   restoration and controlled native-resolution performance checks. No upscaling.
6. Test co-op connectivity with the user's party only after local lifecycle and
   save isolation pass. Record Cloud behavior and sustained play separately.

There is no automatic save conversion, randomizer reroll, mod update or launch
fallback in the present research recipe.
