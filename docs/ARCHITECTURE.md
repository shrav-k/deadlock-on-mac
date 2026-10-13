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
| `game_settings.py` | Narrow, offline display edits with backups; preserves quality and render scale |
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
Only the checkout is versioned. Nothing in a runtime installation, Steam account
directory, crash dump or backup is included in a source release.

Absolute profile paths currently bind a workspace to its location. Consolidation
is an offline operation: close the managed apps, move directories, rewrite only
the managed profile paths, then verify runtime hashes, installation metadata and
launch arguments. Historical logs retain the paths at the time of capture. A
future app should store workspace-relative managed paths and provide a tested
relocation command; arbitrary live folder moves are not supported yet.

## Distribution milestones

1. **Developer preview (current):** source checkout, Python 3.12+, pinned free
   components, explicit setup commands and diagnostic evidence. No claim of
   out-of-box gameplay. The current M2 Max game-startup crash blocks that claim.
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

Game Mode remains independent of the Wine provider. Play uses it by default when
configured with a compatible, signature-verified Apple tool, with an explicit
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
