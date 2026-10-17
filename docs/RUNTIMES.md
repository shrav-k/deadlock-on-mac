# Runtime research and maintenance

Reviewed 2026-10-13. A project description is a claim, not a compatibility test.
No engine has yet passed this repository's full Deadlock gameplay acceptance gate.

| Candidate | Role here | Reason and limits |
| --- | --- | --- |
| [Highball engine](https://github.com/gauthierpiarrette/highball-engine) + [paired DXMT](https://github.com/gauthierpiarrette/dxmt/tree/a44471614f7cf4817e4eee717993eb19e35184b9) | Default free candidate | Published LGPL Wine source and patch series, including cross-process Metal window support. Steam login and graphics probe pass here. Small project; independent reproducible build and full gameplay remain unverified. |
| [Sikarugir Wine engines](https://github.com/Sikarugir-App/Engines) + [DXMT](https://github.com/3Shain/dxmt) | First free candidate | Current standalone Wine 11 package exposes the Mac driver interface DXMT needs. Pinned downloads, separate prefixes. Exact engine build reproducibility remains unverified. |
| [Sikarugir wrapper](https://github.com/Sikarugir-App/Sikarugir) | Comparison option | Active Wineskin successor with several renderers. Creator/launcher are not all under the FOSS license; we use the engine directly instead of adopting its app layer. Its brew cask also clears quarantine and re-signs the app. |
| [Official Wine macOS packages](https://github.com/Gcenx/macOS_Wine_builds) | API-tested candidate | Wine 11.18 passes 32/64-bit notification probes in an isolated prefix. Steam/DXMT/Deadlock remain unqualified. A newer base alone does not establish that integration. |
| [Official CrossOver](https://www.codeweavers.com/crossover) | Optional adapter | Intact signed vendor app, commercial support and D3DMetal/DXMT choices. Paid after trial. Useful comparison if free runtimes fall short. |
| [Decanter](https://github.com/ricardothesillyllama/Decanter) | Architecture reference | Save protection, runtime inventory and recovery ideas. New project, author reports one testing machine. Broad game-manager scope exceeds this Steam-specific project. |
| [steamplay-mac](https://github.com/Drustburn/steamplay-mac) | Research, not baseline | Builds Wine from public sources and integrates native Steam. Native-client injection and update suppression create additional failure modes. We keep Windows Steam unmodified. |
| [kaon](https://github.com/enjihn/kaon) | Research | Native Steam integration, overrides and repair machinery. More invasive than the initial Windows Steam route. |
| [deadlock-launcher](https://github.com/miroshnichenkoai/deadlock-launcher) | Testing reference | Deadlock-specific DXMT observations and diagnostics. Reported results concern other hardware; do not copy global process priorities, audio changes or passwordless sudo. |
| [windows-steam-on-apple-silicon](https://github.com/mirpo/windows-steam-on-apple-silicon) | Research | Sikarugir automation; older runtime pins and rebuild behavior need care. |
| [Whisky](https://github.com/Whisky-App/Whisky) | Excluded as foundation | Archived and explicitly unmaintained. |
| [steam-on-m1-wine](https://github.com/notpop/steam-on-m1-wine) and [play-windows-steam-on-mac](https://github.com/ramiabih/play-windows-steam-on-mac) | Diagnosis references | Document current Steam/CEF and DXMT problems. Their helper replacement and updater-verification workarounds add maintenance burden; our working Highball profile leaves Steam executables unchanged. |

## Free runtime provenance

The default pair is Highball's engine from 2026-10-06, source tag commit
`ac5cc83bb7d90b8fcca8e60a4a37fce2b9ee1d81`, and DXMT commit
`a44471614f7cf4817e4eee717993eb19e35184b9`. The engine builds from the
published LGPL CrossOver 26.3 source tree; it is not the commercial app or its
trial runtime. Its source tarball digest and patches are published. Build tooling
and some dependency downloads are not fully pinned, and we have not reproduced
the release locally. Our lock file pins the selected binary artifacts.

Highball's manifest labels its DXMT build MIT, but the pinned source's `LICENSE`
says LGPL-2.1-or-later. We use that source license rather than repeating the
manifest's incorrect label. No runtime binaries are redistributed here.

The original comparison engine is `WS12WineSikarugir11.0_1.tar.xz`, release asset updated
2026-10-01. DXMT is upstream `v0.80`, not the older Sikarugir DXMT fork. Both
asset hashes were checked against GitHub release metadata. Runtime downloads remain
local and are not committed or redistributed by this repository. Its D3D11 probe
passed, but Steam remained black with GPU and software UI rendering. The failure
matches [DXMT issue 141](https://github.com/3Shain/dxmt/issues/141).

The engine requires support libraries supplied in Sikarugir's Template 1.0.21
archive (including libinotify, FreeType, GnuTLS and GStreamer). The manager pins
that archive too and extracts only its support Frameworks, excluding all bundled
renderers and SikarugirSdk. It never executes the template's launcher or installer.
Process-local library paths connect these libraries to Wine without patching or
re-signing the binaries. Their build provenance and individual licenses are part
of the remaining reproducibility work.

Wine's source license is LGPL-2.1-or-later with individual component notices; see
[Wine's license](https://github.com/Sikarugir-App/wine/blob/master/COPYING.LIB).
DXMT v0.80 is MIT; development after that release changed to LGPL. See the
[versioned license](https://github.com/3Shain/dxmt/blob/v0.80/LICENSE).
macOS, Rosetta and Steam remain proprietary dependencies. The baseline does not
depend on Apple's proprietary D3DMetal or a CrossOver trial.

We have not reproduced the published Sikarugir engine from a uniquely identified
source commit and complete toolchain. That is a durability gap, tracked explicitly
instead of describing the current binary package as reproducible. A later build
recipe must pin source commits, compiler/SDK requirements, patch series and all
dependency hashes, produce an SBOM, and pass the same Steam/game tests. Preserve
licenses and source obligations if distributing a runtime build.

## Upgrade process

1. Check upstream release notes and source changes. Update the versioned artifact
   URL and independently record its digest/provenance. Never use a silent `latest`
   download or automatic fallback to an old version.
2. Run manager tests. Extract a new runtime directory; never modify a working one.
3. Add a new profile with a new prefix. Keep the existing game data and runtime.
4. Install/update Steam normally; test the same Deadlock build and settings.
5. Run `runtime-verify --runtime highball` (or `sikarugir`) to compare installed
   files to the hash-verified archives. Receipts alone are not an integrity check.
6. Record results in the compatibility ledger, including failures. Label candidate
   defaults experimental until the full acceptance gate passes.

Steam updates the game and itself independently. Pinning a Wine runtime does not
freeze Deadlock. CrossOver updates through its vendor app and has separate licensing.
Back up local data and finish Cloud sync before any runtime comparison or migration.

## Source hotfix and qualification lanes

See [the Wine exit backport](WINE-HOTFIX.md) for matched-source builds, provenance,
activation and rollback. See [runtime qualification](QUALITY.md) for candidate
promotion, upstream contributions, broader game scope and the match protocol.
