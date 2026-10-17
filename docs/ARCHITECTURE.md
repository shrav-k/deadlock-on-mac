# Architecture and distribution

The player-facing target is one signed macOS app: choose a tested runtime, install
Windows Steam, sign in, install Deadlock, and play. The current deliverable is an
experimental developer CLI and a local native app preview with bundled Python.
Successful download, installation or checksum tests
must not be described as proof that the game works out of the box.

## Module boundaries

| Module | Responsibility |
| --- | --- |
| `config/runtimes.json` | Named runtime combinations, adapter family, OS minimum and compatibility status |
| `config/runtime-lock.json` | Versioned artifacts, exact digests, extraction layout, source/license provenance |
| `catalog.py` | Validate the catalog and resolve a combination to its component artifacts |
| `runtime.py` | Wine-family and official CrossOver launch adapters; isolated environment and Steam-only game launch |
| `steam.py` | Narrow app manifest parsing and Deadlock data locations; no account authentication implementation |
| `storage.py` | HTTPS downloads, archive validation, immutable installations, integrity checks and atomic state |
| `backup.py` | Offline, game-only snapshots with a file hash manifest |
| `diagnostics.py` | Read-only native dependency inspection, with explicit scope and unresolved libraries |
| `performance.py` | Validated per-profile FPS cap, Wine synchronization and Metal HUD settings |
| `displays.py` / `native/` | Named host displays, guest mapping, offline preparation and Play validation; no macOS display changes |
| `game_settings.py` | Backed-up offline display/FPS/native-rendering edits and allowlisted graphics receipts; display edits preserve quality and render scale |
| `game_mode.py` | Optional Apple-tool status, bounded system-wide Game Mode tests and recovery receipts |
| `game_session.py` / `session_worker.py` | Detached normal-Play lifetime, per-user policy ownership, bottle matching and prior-policy recovery |
| `telemetry.py` | Per-process Metal presentation-interval summaries, excluding other apps and warm-up |
| `cli.py` | Command orchestration, profile creation and selected diagnostics |
| `packaging/` | SwiftUI shell, isolated bundled-Python entry point and pinned app build inputs |
| `tests/native` | Standalone Windows rendering probes, independent of Steam accounts |

Adding another build of an existing Wine family means adding artifact records and
a runtime-set entry. A new family requires an adapter change and contract tests.
Components are deliberately paired: a newer DXMT must not silently replace the
renderer validated with an engine. Official CrossOver remains a separate provider
because it owns bottle setup, updates and licensing.

Profiles are immutable records with dedicated prefixes. An upgrade creates a new
runtime directory and profile. Steam manages its own updates and game builds;
the runtime catalog does not freeze them. A diagnostic launch is not a migration.
Separate prefixes prevent configuration conflicts, not access to the host.

## Workspace and source

The checkout, runtime installations, bottles, installers, developer tools, private
logs, crash dumps, backups and audit evidence live beneath one `Deadlock` folder.
Only the checkout is versioned. Nothing in a Steam account directory, crash dump
or backup is included in a source release. The local app builder can explicitly
include the reviewed, separately licensed Wine hotfix overlay; the main engine,
renderer and support libraries are downloaded. See [workspace ownership and
cleanup](WORKSPACE.md) for folder retention and development-cache policy.

Absolute profile paths currently bind a workspace to its location. Consolidation
is an offline operation: close the managed apps, move directories, rewrite only
the managed profile paths, then verify runtime hashes, installation metadata and
launch arguments. Historical logs retain the paths at the time of capture. A
future app should store workspace-relative managed paths and provide a tested
relocation command; arbitrary live folder moves are not supported yet.

## Distribution milestones

1. **Developer preview (current):** source checkout, Python 3.12+, pinned free
   components, explicit setup commands and diagnostic evidence. No claim of
   out-of-box gameplay. Intermittent startup/session failures, incomplete display
   acceptance and unqualified sustained performance still block that claim.
2. **Packaged preview (local build tested):** a self-contained macOS app/CLI with its own Python
   runtime so players need no Homebrew, Git, pip or compiler. The app bootstrapped
   Windows Steam from an empty workspace; the user signed in and installed Deadlock.
   Public distribution still needs documented
   build reproducibility, checksums, complete component licenses and a software bill of materials.
   Keep runtime/game downloads separate from the app package.
3. **Player release:** sign and notarize the app using a project-controlled Apple
   Developer identity, offer update/rollback paths, and pass fresh-install and
   upgrade tests on the advertised macOS/chip matrix. An unsigned development build
   must not instruct players to disable Gatekeeper.

Do not bundle the commercial CrossOver engine, Steam, Deadlock, credentials or
Apple's separately licensed D3DMetal. Redistribution of LGPL components needs the
corresponding source and license obligations satisfied. Packaging must not silently
change a user's runtime, prefix, Steam account or Cloud-conflict decision.

Game Mode remains independent of the Wine provider. Setup discovers and prepares
a compatible, signature-verified Apple tool; Play uses it by default, with an explicit
opt-out for ordinary Steam launch. The Apple executable is not bundled. A detached
isolated Python worker owns a per-user lock and recovery receipt outside the
workspace, enables the system-wide policy, and asks the existing runtime adapter
to launch through Steam. It matches native Windows game processes by executable
name and bottle working directory (not their environment), then tracks PID plus
start identity without a game-duration timer. The manager can close while it runs.
Normal exit/signals restore the exact prior policy. A failed restore retains its
receipt; recovery/re-adoption is explicit or happens on next Play. SIGKILL/power
loss cannot guarantee immediate cleanup. Native Wine app identity/fullscreen
integration and a supported Apple-tool distribution route remain future work;
this lifecycle feature does not establish native per-game eligibility.
The [Game Mode setup decision](GAME-MODE-SETUP.md) distinguishes Apple's public
native activation path from this private-framework-backed developer-tool override
and records the clean-install qualification required for its Xcode prerequisite.

## Release gates

- Fresh download and extraction; every required artifact is pinned and available.
- Direct and transitive runtime dependency audit, including optional codec paths.
- Current Windows Steam installs, self-updates, signs in, closes and reopens.
- Deadlock installs and launches through that Steam account after a cold restart.
- Menu and private training render; keyboard, mouse, audio and expected account
  data work. Then user-verified friends/party/match testing, with Cloud behavior
  recorded precisely rather than assumed.
- Updates preserve data; offline backups verify; recovery is tested in a disposable
  copy. Interrupted downloads and failed upgrades leave the working profile intact.

Automated tests, runtime probes and human gameplay results stay separate in the
compatibility ledger. Do not promote a version based only on a successful install.

## Deployment readiness — 2026-10-16

**The current workspace is a working development installation, not yet a
player-ready distribution.** The local preview includes its own Python, native
helpers and the reviewed exit overlay. A new player should eventually need only
the app, the supported Mac prerequisites, a Steam account and game entitlement.
Steam login/Guard and game downloads remain normal first-run steps.

| Area | Evidence and remaining work |
| --- | --- |
| Workspace integrity | After cleanup, all 5,641 files/links in the three active runtime components matched pinned archives; the separate exit overlay verified. The bundled CLI found the existing Steam/game install and generated the correct Steam launch command without executing it. |
| Fresh installation | The app previously bootstrapped Windows Steam in an empty workspace, followed by user login and game installation. On October 16 a fresh download of Valve's installer matched the pinned digest. That check did not repeat setup, account login or gameplay. Repeat the whole flow for the release candidate. |
| Player dependencies | The 0.4.2 preview bundles Python, certificates, display helpers and matching FFmpeg. Game Mode discovers compatible Apple tools automatically, checks signature/status before setup and prepares a local copy for Play/recovery. A Mac without one still needs compatible Xcode from Apple or an explicit opt-out; no file selection or global toolchain switch is required. |
| Runtime libraries | The 0.4.2 fix resolves the three missing FFmpeg imports with a source-inclusive private package. Its x86_64 audio decode and Wine's 64/32-bit media bridges pass; the 31-module direct-import scan has zero unresolved entries. In-game media paths and the broader transitive/plugin audit remain separate qualification work. |
| Launch/exit | Earlier menu, normal exit, Game Mode restoration and actual manager quit/exit controls have passing observations. Current cold starts pass on both display configurations, but the earlier Steam startup stall remains unisolated. Orphan-overlay recovery is separately reported from normal shutdown; see the [investigation](STARTUP-INVESTIGATION.md). |
| Displays/performance | Built-in Retina borderless has a prior visual pass. The new automatic display policy still needs its visual runs. Exclusive fullscreen and LG game-menu coverage remain unresolved; external gameplay and sustained benchmarks are pending. |
| Distribution | The current app is ad-hoc signed, not notarized. Complete signing, update/rollback, corresponding-source/license inventory and SBOM work. Source-only bootstrap does not include the exit overlay unless it has been built or supplied. |
| Portability | Profile paths are absolute. Copying this folder to another user's Mac is not a supported installer or migration. A relocation/data migration command requires tests. |

The installed game's manifest reported build `25939744` during the offline audit;
that does not extend older gameplay acceptance to this build. Cloud and multiplayer
remain unverified. The initial cleanup started no runtime sessions. The subsequent
media fix ran owned probes in disposable Wine prefixes, without Steam, Deadlock or
display grids. See the [compatibility ledger](COMPATIBILITY.md) for the underlying
historical runs and [quality protocol](QUALITY.md) for promotion criteria.

## Evolving into a launcher with game recipes

The current implementation is still Deadlock-specific: the Steam app ID,
executable matching, save/config paths, setting adapters and some display probes
assume Deadlock. Runtime adapters are reusable foundations, not proof that an
arbitrary Steam title is supported. Keep Deadlock as the first qualified recipe
and extract shared behavior only behind tests that preserve its working setup.

The proposed boundary is one launcher core plus versioned game recipes:

| Layer | Owns |
| --- | --- |
| Launcher core | Artifact verification, runtime/provider adapters, Steam handoff, process lifecycle, Game Mode ownership/restoration, host-display policy, backups, diagnostics and benchmark collection |
| Runtime set | Exact Wine/renderer/support pairing, platform constraints, provenance and narrowly scoped hotfix overlays; independent of the game's Steam update channel |
| Game recipe | Steam app ID, process identities, dependency requirements, config/save adapters, supported runtime sets, display/quality presets, known issues and acceptance scenarios |
| User installation | Chosen game/runtime recipe versions, prefix, Steam-managed files/account state, display choice and user overrides; private and separate from recipes |

CodeWeavers' CrossTie application profiles provide a useful precedent: they
describe Steam IDs, installation detection, bottle preferences/grouping and
compatibility status. Our core/recipe split is a proposed design informed by that
pattern, not an implementation of CrossTie or a compatibility claim about its
recipes. [CodeWeavers application-profile documentation](https://support.codeweavers.com/en_US/crosstie-data-startpage/c4-data-application-profile)

Start with a validated declarative recipe format and narrow, reviewed adapters
for game-specific edits. Do not turn downloaded recipes into unrestricted shell
scripts. Back up affected settings, preserve user overrides, make changes
reversible and reject unknown schema versions. A recipe should declare required
capabilities and tested combinations, not blanket registry or DLL overrides.

Share immutable runtime files and download caches. Isolate prefixes where games
need conflicting Windows, DLL, DPI or runtime settings; Wine's Retina setting is
currently bottle-wide. Explicit compatibility groups can eventually share Steam
environments. Shared game-library support needs ownership, update and backup tests
before it can replace today's managed default library. Do not create another full
game copy for every benchmark candidate by default.

Steam continues to own authentication, entitlement, downloads, updates, friends
and whatever Cloud support each game provides. Compatibility must be advertised
per qualified title and stack, not as “any Windows game”: renderer/API, DRM and
anti-cheat requirements can prevent a title from working. Generalizing the manager
does not remove those constraints.

Keep the initial extraction in this repository:

1. Qualify Deadlock's fresh-install, update/recovery and built-in/external display
   lifecycle; complete gameplay benchmarks when testing resumes.
2. Introduce a `GameDefinition`/recipe boundary behind the existing commands.
   Test invalid IDs/paths, process and prefix isolation, rollback, data preservation,
   missing dependencies and migration from the current Deadlock-specific state.
3. Add one second game to exercise different settings/dependency needs before
   declaring the abstraction reusable. Use shared runtime contract tests plus
   per-game install/menu/exit and opt-in gameplay scenarios.
4. Move to the planned organization repository once the stable scope is agreed.
   Preserve attribution/history, release evidence and user-data migration. Choose
   stable bundle/state identities and signing/update ownership before public release.

Performance qualification should compare exact runtime, renderer, recipe, game
build, OS, hardware, output size, render scale and power/thermal state. Separate
first-run shader work from warmed runs; collect frame-time percentiles, stutters,
crashes and repeated results rather than ranking average FPS alone. Automated
probes and lifecycle checks cannot replace game-specific interaction and real-match
acceptance. Upstream Wine patches should keep minimal reproducers and matched-build
tests; a Deadlock workaround must not silently become a default for every game.

No organization migration, new repository or universal-game implementation is
part of the current cleanup.

### Next initiative: Elden Ring with Seamless Co-op

The next recipe will exercise Elden Ring plus its optional Seamless Co-op
integration alongside Deadlock. This is planned scope, not current compatibility
or installation support. First verify the then-current upstream installation,
launch and version requirements; do not infer them from Deadlock's Steam URI flow.

Extract the existing behavior behind a tested `GameDefinition` before adding the
second game: Steam app identity, executable/process ownership, settings/save
adapters, launch strategy, dependencies and acceptance scenarios. Preserve the
current Deadlock command defaults, profile identifiers and data with an explicit,
versioned migration. Shared lifecycle, display, capture/input, Game Mode and
telemetry services must receive a game definition rather than hardcoded paths.

Model a mod as a separately versioned, optional recipe component with upstream
provenance, verified artifacts, owned files and reversible install/update/remove
operations. Keep user configuration, secrets and save data outside the recipe.
Test official-game and mod launch routes independently; qualify their Steam
session requirements before sharing a bottle or library. Do not duplicate large
game installations merely to compare runtime candidates.

Acceptance needs two layers: core contract tests for process isolation, display
selection, policy restoration, backup/rollback and migration; then per-recipe
installation, menu, clean exit, native-resolution visual checks and repeatable
offline performance scenarios. Multiplayer/co-op acceptance is a separate later
step. A Deadlock-specific DLL/config workaround must never become an implicit
global override for the new game.
