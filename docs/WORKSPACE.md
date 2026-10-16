# Workspace ownership and cleanup

The `Deadlock` directory is both a local installation and a development workspace.
Players should eventually receive one app that creates its managed data, not a
copy of this entire directory. The current local app is
`Builds/Deadlock Manager.app`; `Builds/Previous` holds one verified rollback.

## What belongs here

| Folder | Role | Retention |
| --- | --- | --- |
| `Bottles/` | Windows environments, Steam, installed games, account/session data and game settings | Required for existing installations. Never treat as a cache or remove automatically to reclaim space. |
| `Runtimes/` | Immutable engines, paired renderers/support libraries and separately verified overlays | Keep everything referenced by an active profile or enabled hotfix. Remove unreferenced comparison installations only after checking live processes and provenance. |
| `DeadlockData/` | Profiles, preferences, display preparation, recovery records, logs and research receipts | Required state. Only explicitly reviewed historical evidence/logs are eligible for retention cleanup; active session/recovery records are not disposable. |
| `Tools/` | Locally supplied Apple Game Mode tool and temporary developer build directories | The configured Game Mode tool is required for that launch preference. Compilers/object trees are optional and should be removed after verified outputs and evidence are retained. |
| `DeadlockBackups/` | Small local game-data snapshots with manifests | Recovery data, not a runtime prerequisite. Retain verified copies; never delete the only backup as generic cleanup. |
| `Builds/` | One current app, one rollback and bounded build receipts | Required to use this local preview. See the [build publication policy](../packaging/README.md); avoid version-named app piles. |
| `Downloads/` | Hash-checked compressed installers, runtime/source/compiler archives | Re-downloadable cache; not needed to play an already installed profile. Retain pinned inputs needed for offline repair/reproducibility, or prune them explicitly when space matters. Never repin a changed download automatically. |
| `deadlock-on-mac/` | Maintained source, tests, recipes and documentation | Needed for development/source CLI, not for running the self-contained app. Commit source only, not private workspace data. |

The October 16 installation retains exactly one active bottle and four runtime
directories: Highball Wine, its paired DXMT, Sikarugir support libraries and the
reviewed Highball exit overlay. These are complementary components, not four game
installations. Removing the inactive Sikarugir Wine engine does not make its shared
support libraries redundant.

`Tools/game-mode-investigation/gamepolicyctl` has a historical directory name but
is an active prerequisite referenced by local settings. Keep its path until a
tested settings migration changes it. Likewise, do not rename/move bottles or
runtime roots for cosmetic reasons: current profiles use absolute paths.

Some normal macOS caches/preferences and the per-user Game Mode ownership/recovery
receipt live outside the workspace. The folder is not a complete portable snapshot
of an active session. Close sessions and inspect recovery before relocation.

## Cleanup procedure

1. Close the manager, managed Steam/game, Wine diagnostics and detached session
   workers. Check profile/runtime/hotfix references, not just app windows. Acquire
   the workspace lock before editing managed storage.
2. Inventory exact paths and sizes. Classify account/game state, active components,
   recoverable inputs and disposable derived outputs. Refuse symlink paths and
   preserve unknown contents for inspection; do not use broad deletion globs.
3. Keep pinned compressed source/compiler/runtime inputs, licenses, patch recipes,
   accepted output digests and diagnostic logs before removing expanded build
   trees. A source archive must be read back and checked against its manifest.
4. Record an allowlisted plan and provenance before removal. Consolidate small
   historical reports under `DeadlockData/research/<investigation>/`; do not move
   operational session state into research. Old absolute paths in logs remain
   historical evidence rather than being rewritten.
5. Verify active runtime hashes, overlay hashes, app integrity/signature, packaged
   `doctor`, Steam launch dry-run and unchanged Game Mode policy afterward. A
   successful dry-run does not establish visible launch or gameplay acceptance.

Do not automatically delete Steam shader caches during cleanup: they belong to
the installation and their removal changes the next performance test. Do not
remove `Builds/.preview-transaction` as temporary clutter; it may hold a recoverable
interrupted publication. No general-purpose workspace prune command exists yet.
A future storage UI should show reclaimable sizes, active references and a review
plan before removing data, with account/game storage excluded by default.

## October 16 cleanup record

The audited local cleanup reclaimed **6.16 GiB** of allocated workspace storage.
It removed duplicate expanded Wine/compiler/build trees, two disposable Wine-only
test prefixes, inactive CrossOver/development-Wine/Sikarugir/upstream-DXMT
installations, and obsolete extracted audit payloads. Two identical patched source
trees were consolidated into one compressed archive with 11,087 verified entries.
Compressed comparison installers and source/build inputs remain in `Downloads`.

Private receipts, archive manifests and retained investigation logs are under
`DeadlockData/research/workspace-cleanup-2026-10-16/`. The old top-level audit folder
and completed investigations under `Tools` were moved there. Active game/account
data, backups, shader caches and the Apple tool were not removed. The installed
0.4.1 app was preserved; this documentation change did not generate another app.

Approximate remaining allocated storage at that audit:

| Contents | Size |
| --- | --- |
| Active bottle, including Steam/game | 39.0 GiB |
| Active runtime components | 1.21 GiB |
| Compressed download/build-input cache | 1.41 GiB |
| Current and rollback apps | 137 MiB |
| Private state, logs and archived research | 226 MiB |
| Source, backups and Apple tool | Under 5 MiB combined |

Sizes are an observation, not quotas; Steam updates and diagnostic logging change
them. Public distribution and general-game architecture are tracked separately in
[deployment readiness](ARCHITECTURE.md#deployment-readiness--2026-10-16).
