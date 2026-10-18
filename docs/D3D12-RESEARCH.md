# Free D3D12 qualification

Investigated 2026-10-17 on M2 Max, macOS 26.6.2. This is a renderer qualification
record, **not an Elden Ring or Seamless Co-op compatibility pass**.

## Decision

The next game-specific experiment should use **Highball Wine 11 with D3DMetal
4.0 beta 2 in a separate prefix**. That combination passed the standard D3D12
probe on this Mac. Sikarugir Wine 11 with the same renderer also passed the
offscreen shader/readback test. Neither requires a CrossOver trial or paid
CrossOver installation. Deadlock remains on its existing Highball/DXMT stack.

The Apple renderer is proprietary and this version is a beta. This is an unpaid
candidate, not a wholly open-source renderer we can patch. No default runtime,
installed manager, existing profile, game setting or save was changed. The
research-only Elden Ring launch gate remains closed.

## Measured results

| Separate test stack | Local result | Disposition |
| --- | --- | --- |
| Highball `20261006` + metalsharp VKD3D-Proton macOS `v1.0` | Hardware device creation, clear/copy, fences and exact red-pixel readback pass; a standard graphics PSO fails with `E_INVALIDARG` | Reject as a drop-in backend |
| Same fork, diagnostic executable using its nonstandard PSO layout | The same shader draw and green-pixel readback pass | Confirms the API-layout mismatch; not a compatibility workaround for games |
| Gcenx GPTK `3.0-3`, bundled Wine 7.7 + D3DMetal 3.0 | Standard shader pipeline and exact green-pixel readback pass | Useful control, not a qualified current Steam environment |
| Highball or Sikarugir Wine 11 + those D3DMetal 3.0 bridge files | Factory/adapter query succeeds; device creation terminates with an access violation | Reject these tested combinations |
| Sikarugir `WS12WineSikarugir11.0_1` + template's D3DMetal 4.0b2 | Standard shader pipeline and exact green-pixel readback pass | Comparison candidate |
| Highball `20261006` + template's D3DMetal 4.0b2 | Standard shader pipeline/readback and 60 windowed flip-discard presents pass; **three successive runs in a fresh test prefix pass** | Preferred next qualification candidate |

The probe requests a hardware adapter and FL12_0, executes a real GPU clear and
copy, waits on a fence, and checks all 16 RGBA pixels. Its default shader case
compiles ordinary DXBC vertex/pixel shaders, creates a standard graphics PSO,
draws a full-coverage green triangle and verifies the result. `--present` adds
60 windowed frames, bounded GPU waits and window destruction. Each of the three
qualification runs returned zero. The original six Deadlock configuration
fingerprints remained identical.

This small synthetic workload does not establish performance, DXIL/SM6 coverage,
large resource/descriptor correctness, fullscreen, HDR, display switching, Steam
UI compatibility, game startup, mod injection, Cloud behavior or co-op networking.
It never starts Steam or a game, imports saves, changes Game Mode or enables
upscaling. Successful process completion is not visual acceptance of the game.

## Why the VKD3D fork is not ready

The released fork's test header inserts mesh/amplification shader bytecode fields
into `D3D12_GRAPHICS_PIPELINE_STATE_DESC`. Microsoft's published legacy structure
does not contain these fields; mesh shader pipeline streams are a separate API.
With the standard structure our PSO fails, reporting an invalid inactive render
target format. Changing only the diagnostic's structure to the fork's layout
makes the same shader/readback case pass. Do not change game binaries or standard
headers to make a qualification test appear green.

The public build instructions also require custom source trees without providing
complete pinned clone instructions for those modified trees. The release binary
can be tested, but we have not established a reproducible source rebuild. Fixing
the public ABI and obtaining the complete corresponding sources are prerequisites
to maintaining this route.

Sources: [Microsoft PSO ABI](https://learn.microsoft.com/en-us/windows/win32/api/d3d12/ns-d3d12-d3d12_graphics_pipeline_state_desc),
[fork's custom descriptor](https://github.com/metalsharp/VKD3D-Proton-MacOS/blob/main/scripts/probes/d3d12_pso_desc_ms.h),
[fork build instructions](https://github.com/metalsharp/VKD3D-Proton-MacOS/blob/main/docs/Development.md).

Upstream [vkd3d-proton](https://github.com/HansKristian-Work/vkd3d-proton) and
[MoltenVK](https://github.com/KhronosGroup/MoltenVK) are separate projects; a Vulkan
version number alone does not prove that the required extensions, descriptor
limits and behavior are implemented. Do not apply the fork's result to upstream.

## Provenance and licensing

- Highball engine: existing pinned `highball-wine-20261006` package from the
  runtime catalog, read-only. The Deadlock-specific DLL overlay was not loaded
  into the D3D12 experiments.
- Renderer: D3DMetal **4.0b2** from the reviewed
  [Sikarugir Template 1.0.21 release](https://github.com/Sikarugir-App/Template/releases/tag/v1.0).
  Archive SHA-256: `bbe996e4e4375318485953d0c7818b7b4b0a4dc1f13303bcc584f99f7602f78d`.
  Only its complete `renderer/d3dmetal` subtree was staged in private research
  storage, including license/notices and the entire framework. Its framework
  passes strict code-signature verification through Apple's signing chain.
- D3DMetal framework binary SHA-256:
  `f5b56df1b8fe8b364dd9530651a3769c8aed948bd343be3b4510604d503e2bad`.
  `libd3dshared.dylib`: `1582e7ceef7f495df4bebf7f06a49aef130233f8a2e9a8971e35affafeb76ec0`.
- Rejected VKD3D archive SHA-256:
  `f1eabd729a65f0a62bcba9a3a8054bdef9895981351dc8896993a8cffa12299c`.
  [Release and upstream qualification scope](https://github.com/metalsharp/VKD3D-Proton-MacOS/releases/tag/v1.0).
- GPTK 3 comparison archive SHA-256:
  `d377683937340f914823dbb2e1252b329cbf834ff58907d0293db8cebf0e392e`.
  [Gcenx release](https://github.com/Gcenx/game-porting-toolkit/releases/tag/Game-Porting-Toolkit-3.0-3).

Apple's supplied agreement permits development/testing/evaluation on Apple
hardware and describes non-commercial distribution of the framework and
redistributables. It restricts modification and other uses. Treat the renderer as
a separately licensed dependency, preserve its terms/notices, and do not infer
that the launcher's open-source license covers it. The launcher does not bundle
Apple or campaign binaries in Git. Review the exact payload's agreement before
designing public distribution; unrestricted everyday-use rights should not be
assumed from a free download.
[Supplied agreement](https://github.com/Sikarugir-App/Sikarugir/blob/main/D3DMetal/4.0/License.pdf),
[Apple's toolkit](https://developer.apple.com/games/game-porting-toolkit/).

Use the [Sikarugir GitHub organization](https://github.com/Sikarugir-App/Sikarugir)
as the project source. Its maintainers explicitly disavow the similarly named
`sikarugir.com` website. No installer was fetched from that site.

## Reproduce the owned probe

Build without installing any renderer or touching Wine:

```sh
python3 packaging/build_d3d12_probe.py \
  --output /absolute/path/to/private/probe \
  --downloads /absolute/path/to/download-cache
```

The builder verifies the pinned LLVM/MinGW archive, uses warnings as errors,
compiles the published x64 ABI and writes a source/executable/compiler receipt.
CI compiles the probe but cannot claim a hardware pass. Local GPU runs are opt-in.

For the tested Highball/D3DMetal combination, start from a clean child environment
and a **new, dedicated test prefix**, not an existing game or Steam bottle. Keep
the template's `wine` and `external` directories together. The required renderer
configuration is:

| Child environment variable | Tested value |
| --- | --- |
| `WINEPREFIX` | New private test-prefix directory |
| `WINEDLLPATH_PREPEND` | `<d3dmetal>/wine` |
| `WINEDLLPATH` | `<d3dmetal>/wine:<highball>/lib/wine` |
| `WINEDLLOVERRIDES` | `d3d12,dxgi=b;winemenubuilder.exe=d` |
| `CX_APPLEGPTK_LIBD3DSHARED_PATH` | `<d3dmetal>/external/libd3dshared.dylib` |
| `DYLD_FRAMEWORK_PATH` | `<d3dmetal>/external` |
| `DYLD_FALLBACK_LIBRARY_PATH` | Renderer external directory, pinned support directory, Highball Unix-library directory, support GStreamer libraries, `/usr/lib` |
| `DYLD_FALLBACK_FRAMEWORK_PATH` | Pinned support directory, `/System/Library/Frameworks` |
| `WINEMSYNC`, `WINEESYNC` | Both `0` for this controlled comparison |
| `D3DM_ENABLE_METALFX`, `D3DM_SUPPORT_DXR`, `D3DM_MTL4` | All `0`; native rendering, no ray tracing, Metal 3 on this OS |

The default library path order matters. Adding the **entire Wine 7.7 library
tree** as an override mixes core Wine modules and is incorrect. Do not transplant
that tree into a modern runtime. The Sikarugir comparison uses its documented
`WINEDLLPATH_D3DMETAL`/host marker instead of Highball's prepend mechanism.

After initializing only that test prefix with `wine wineboot -u`, run
`wine /absolute/path/to/d3d12-probe.exe --clear-only`, then the default shader
case, then `--present`. Apply an external timeout to every process; the probe
also bounds each fence wait. Read the log and require both zero exit status and
the appropriate PASS markers. A prefix-scoped wineserver shutdown is only
appropriate for this disposable diagnostic prefix, never the working bottle.

## Before enabling Elden Ring Play

1. Add a separately pinned renderer/provider recipe with capabilities, licensing,
   integrity checks, prefix ownership and explicit compatibility gates. Do not
   change the meaning of an existing DXMT profile.
2. Qualify current Windows Steam installation, visible sign-in/library, update,
   clean exit and account continuity with that renderer. Test Steam's D3D11 UI
   separately from the D3D12 game path.
3. Use owned Elden Ring files, confirm the exact game/mod versions, and test the
   selected standalone or Mod Engine launch strategy. Keep anti-cheat routing
   and the mod's save namespace consistent with the author's instructions.
4. Qualify menu, exit, Game Mode restoration, display/input behavior, then native
   resolution gameplay and co-op. Keep the private campaign import explicit and
   backed up. No save migration is part of renderer setup.

The launcher monorepo can now carry these independent game adapters. Moving it
to a new organization repository and archiving the old fork should wait for the
user's destination and the game-specific qualification result.
