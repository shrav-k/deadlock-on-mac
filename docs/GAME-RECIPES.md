# Shared launcher and game recipes

## Repository decision

Use a **source monorepo with separate private content packs**. Keep shared runtime
services, the macOS app, reviewed game adapters and contract tests together. Keep
personal saves, session passwords, generated randomizer worlds and recovery
archives in the user's private campaign storage. A game adapter is source code;
a campaign is data with a different owner, update policy and privacy boundary.

| Layout | Benefit | Cost / decision |
| --- | --- | --- |
| Core repo plus a repo per game adapter | Independent release/maintainer teams | Adds package publishing, API-version coordination and cross-repo CI before the interfaces have stabilized; defer |
| One repo containing source and all campaign data | One checkout | Large clones and backups, private data mixed with distributable source, coupled updates; avoid |
| One source monorepo plus private campaign packs | Atomic core/adapter changes, shared tests, private campaign ownership | Requires a validated pack manifest/import boundary; recommended |

The intended organization-repo layout is:

```text
apps/macos/                  native UI, packaging and signing
launcher/core/               Wine/providers, Steam, lifecycle, display, telemetry
launcher/games/deadlock/     settings, data locations, qualified overrides
launcher/games/elden_ring/   standalone/mod launch strategies, settings/save adapters
recipes/                    game/component metadata and compatibility records
tests/core/                 lifecycle, isolation, rollback and migration contracts
tests/games/                per-game fixtures and opt-in acceptance scenarios
docs/                       installation, research and qualification evidence
```

These are logical boundaries, not a request to rename installed app/state paths.
The current package name and signed app identity remain stable while the first
extraction is validated. Split a library into its own repo later only when an
independent consumer or release cadence justifies a versioned public API.

## Implemented boundary

- `core/wine.py` owns provider/environment setup and Steam command construction.
  `core/steam.py` owns manifest parsing and app-specific Steam queries.
- `config/games.json` contains versioned definitions. `games/__init__.py` validates
  identities and dispatches only reviewed, explicitly allowlisted adapters; it
  does not import arbitrary code named by downloaded data.
- `games/deadlock.py` owns the VDF graphics/FPS/native-rendering schema, SDL path
  and backup locations. `game_settings.py` is a compatibility dispatcher.
- `games/elden_ring.py` is explicitly research-only. Unsupported writes, backup
  assumptions and Play fail before touching game files or enabling Game Mode.
- Session/process matching, capture, benchmark metadata and recovery receipts use
  the selected game identity. The `deadlock` capture target remains an alias for
  existing workflows; `game` resolves from the profile.
- Existing imports of `runtime` and `steam` resolve to the shared implementation.
  DLL hotfix eligibility also includes the game recipe; the reviewed Deadlock
  overlay is not automatically applied to Elden Ring.

Game ID and mod variant are distinct from a runtime profile. One profile still
owns one prefix and one game binding. Future campaign selection must not rebind an
existing profile or share a bottle without testing its DLL/DPI requirements.

## Compatibility and migration

Existing schema-1 profiles retain implicit `deadlock` semantics and are read
without rewriting them. Existing profile IDs, prefix paths, Steam libraries,
backups, display choices, settings and bundle identifiers remain unchanged.
New schema-2 profiles record `game_id` and `game_recipe_version`; unknown versions,
incomplete bindings and attempts to rebind legacy profiles are rejected. Future
recipe changes require an explicit tested migration; this change performs none.

Legacy session/display/benchmark/capture receipts without a game binding mean
Deadlock. New receipts include both fields. Cross-game adoption or replay is
rejected. The existing per-user Game Mode policy owner remains shared: different
games must not create competing global overrides.

The current GUI remains the qualified Deadlock preview. Inspect the catalog from
source or the packaged CLI without installing anything:

```sh
python3 bin/deadlock-mac games
python3 bin/deadlock-mac game-info elden-ring-seamless
```

An explicit `profile-create --game elden-ring-seamless` creates metadata in a new
profile only. It does not install a game or establish graphics compatibility.
Opening Steam/installing its app uses app ID 1245620; **Play is blocked** until a
D3D12 stack, the selected mod launch route and lifecycle have been qualified.
The ordinary Elden Ring Steam URI must never stand in for a mod launch.

## Private campaign integration contract

A future local pack descriptor should identify the game/recipe revision, exact
game/mod/component versions, content hashes, supported launch strategy and save
namespace. Secrets and machine-specific paths remain outside shareable reports.
Only owned files may be installed/removed; generated launch configs are local.
An adapter must not execute a pack's arbitrary shell/PowerShell scripts implicitly.

Keep a pre-generated randomizer world fixed; do not reroll it during installation.
Separate the co-op campaign and optional alternate profiles by save namespace,
settings and launch configuration. Do not import saves or invoke save-editing tools
as part of basic launcher setup. A save transfer is a separately reviewed,
backed-up operation with ownership, conflict and rollback checks.

No content-pack importer, campaign migration, new repo, mod installation or
second-game gameplay claim is included in this extraction. See
[Elden Ring requirements](ELDEN-RING.md) for the next qualification sequence.
