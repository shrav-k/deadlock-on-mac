# Install and use your existing Steam account

Requirements: Apple Silicon, macOS 15 or newer, Rosetta 2, Python 3.12 or newer,
and at least 80 GiB free. Current runtime testing is on an M2 Max with macOS 26.6.2.
Older supported OS versions are not yet tested here. Use macOS's normal Rosetta
installation flow if needed; this manager does not silently accept its license.

Clone this repo inside `Projects/Games/Deadlock`. From the repository:

```sh
python3 bin/deadlock-mac bootstrap
python3 bin/deadlock-mac steam
```

`bootstrap` checks the Mac, disk space and Rosetta, then combines runtime installation,
profile creation and Steam setup. The lower-level `runtime-install`, `profile-create`
and `setup` commands remain available. Runtime installation fetches the pinned Highball Wine engine and paired DXMT build,
plus Sikarugir support libraries,
checks their hashes, and extracts them under `../Runtimes`. `setup` initializes
`../Bottles/highball` and installs the official Windows Steam client. Downloads, state,
game files and backups stay outside this repository. macOS/Wine can still create
ordinary per-user caches and preferences outside Games.

The [local app preview](../packaging/README.md) offers the same sequence with buttons
and its own pinned Python runtime. Players using that app need no Homebrew, Git,
pip or compiler. Its first Steam startup can take several minutes while the client
updates; an initially absent window does not establish a rendering failure.

Log into **your existing Steam account** in the Windows Steam window. Use Steam
Guard or the Steam Mobile QR flow yourself. You do not need another invitation if
that account already has Deadlock. Allow Steam to update, then:

```sh
python3 bin/deadlock-mac install
python3 bin/deadlock-mac launch --dry-run
python3 bin/deadlock-mac launch
python3 bin/deadlock-mac doctor
```

Alternatively select Deadlock in that Steam library and click Install or Play.
The manager always asks Steam to launch app **1422450**. The native Mac Steam
client cannot install a native Mac version of Deadlock; Windows Steam inside Wine
downloads Valve's Windows build. Keep the managed default Steam library for this
first version; diagnostics and backups do not yet discover external libraries.

For the first game launch, leave display overrides unset. A clean-install test
with forced 1080p fullscreen launch arguments crashed; a normal Steam retry reached
the menu with the same FPS cap and HUD. Causation is not established. Change output
resolution through the game's settings after reaching the menu, and verify it there.

## Account data, Cloud and friends

Use the same account on every test profile. Keep Steam online and enable Steam
Cloud globally and for Deadlock **if its Properties page offers the option**.
Deadlock's public store page does not currently advertise Steam Cloud. Do not
assume graphics settings, bindings or all progress are synchronized. Verify account
data in game, distinguish server-held data from Cloud files, and back up local data.

Let the other computer finish syncing before starting this one. If Steam presents
a Cloud conflict, stop and choose deliberately after checking timestamps; the
manager never chooses a side or replaces your files. Wait for synchronization to
finish when exiting before testing another runtime.

Friends, invites and multiplayer use the real Steam client and Valve's game. Test
an invite and a party with a friend before calling multiplayer verified. Merely
starting Steam or reaching the menu is not enough. Future game or anti-cheat updates
may break compatibility independently of the manager.

## Compare another runtime

Profiles are immutable and own distinct prefixes. They can share downloaded
runtime binaries, but never share a live Wine prefix. The older candidate can be
installed separately for comparison; its Steam login UI failed our M2 Max test:

```sh
python3 bin/deadlock-mac runtime-install --runtime sikarugir
python3 bin/deadlock-mac --profile sikarugir profile-create --runtime sikarugir
python3 bin/deadlock-mac --profile sikarugir setup
```

Add an optional licensed or
trial official CrossOver app with:

```sh
python3 bin/deadlock-mac --profile crossover profile-create --crossover '/path/to/CrossOver.app'
```

In CrossOver, set **Settings → System Integration → Bottle Folder** to the same
`Games/Deadlock/Bottles` directory. Install its built-in Steam recipe in a bottle named
`crossover`; do not reuse another profile. CodeWeavers also documents the `BottleDir`
preference if its folder chooser is unavailable. Sign into the same Steam account,
then use `--profile crossover steam`, `--profile crossover install`, or
`--profile crossover launch`. Select graphics settings in CrossOver itself.

CrossOver's trial ends after 14 days; it is not the unpaid baseline. Purchased
versions remain usable after their support/update entitlement ends. There is no
trial reset or extraction of its commercial runtime in this project.

## Backups

Exit Steam and all Wine apps first, then:

```sh
python3 bin/deadlock-mac backup
```

This creates a private, timestamped archive in `Games/Deadlock/DeadlockBackups`, containing
Deadlock's `Steam/userdata/<account>/1422450` and installed `game/citadel/cfg` files,
plus a file hash manifest. Other games, Steam authentication files and client logs
are excluded. The manager conservatively refuses while Wine is running.

These snapshots are not full bottle backups or proof of a Cloud upload. Store a
separate full bottle copy before runtime migrations (CrossOver offers bottle
archives). There is deliberately no automatic restore: inspect the archive, keep
a second copy of current data, exit Steam, and restore only the files you intend.

## Sources

- [Valve: Steam Cloud](https://partner.steamgames.com/doc/features/cloud)
- [Deadlock on Steam](https://store.steampowered.com/app/1422450/Deadlock/)
- [CodeWeavers: install Steam](https://support.codeweavers.com/installing-steam-in-crossover)
- [CodeWeavers: bottle storage](https://support.codeweavers.com/en_US/change-the-bottle-directory-in-crossover-mac)
- [CrossOver licensing](https://www.codeweavers.com/store/licensing)
