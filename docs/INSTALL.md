# Installation, Steam and Game Mode

This is the canonical setup guide. The active development branch is
`maintain/free-steam-runtime-manager`, tracked by [draft PR #1](https://github.com/shrav-k/deadlock-on-mac/pull/1).
The fork's default `main` still has the original upstream installer; use the branch
above until the maintained manager is merged. No public player-ready app release
is available yet.

## Choose your installation path

| Path | What you need | Sequence |
| --- | --- | --- |
| Built local app preview | Apple Silicon, macOS 15+, Rosetta 2, 80 GiB free | Select workspace → Set up Steam → Open Steam → sign in → Install Deadlock → Play |
| Source checkout | The same, plus Git and Python 3.12+ | Clone the maintained branch, then run the commands below |
| Build an app yourself | Source prerequisites plus a compatible Swift compiler/macOS SDK | Follow [app packaging](../packaging/README.md), then use the app sequence |

Game Mode during Play is enabled by default and requires a compatible Apple-signed
`gamepolicyctl`. Select it in the app's Game Mode panel before the first Play. To
play without that tool, turn off **Enable during Play** or use the CLI's
`launch --without-game-mode`. Installation itself does not require Xcode. On an existing
working installation, skip setup/download and use Open Steam → Play. Do not
bootstrap a running Wine environment.

## Source installation

Requirements: Apple Silicon, macOS 15 or newer, Rosetta 2, Python 3.12 or newer,
and at least 80 GiB free. Current runtime testing is on an M2 Max with macOS 26.6.2.
Older supported OS versions are not yet tested here. Use macOS's normal Rosetta
installation flow if needed; this manager does not silently accept its license.

Clone this repo inside `Projects/Games/Deadlock`:

```sh
mkdir -p ~/Projects/Games/Deadlock
cd ~/Projects/Games/Deadlock
git clone --branch maintain/free-steam-runtime-manager https://github.com/shrav-k/deadlock-on-mac.git
cd deadlock-on-mac
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

Alternatively select Deadlock in that Steam library and click Install. Use the
manager's **Play** for automatic Game Mode; clicking Steam's own Play button directly
does not start the manager's watcher. If the game is already running, manager Play
can attach the watcher without launching another copy.
The manager always asks Steam to launch app **1422450**. The native Mac Steam
client cannot install a native Mac version of Deadlock; Windows Steam inside Wine
downloads Valve's Windows build. Keep the managed default Steam library for this
first version; diagnostics and backups do not yet discover external libraries.

For the first game launch, leave display overrides unset. A clean-install test
with forced 1080p fullscreen launch arguments crashed; a normal Steam retry reached
the menu with the same FPS cap and HUD. Causation is not established. Change output
resolution through the game's settings after reaching the menu, and verify it there.

## Establish a baseline

After the first game launch has created its settings, close Deadlock, Windows
Steam and all Wine apps. Save both the renderer's requested limit and the game's
actual game/menu limits:

```sh
python3 bin/deadlock-mac performance --fps-cap 60 --hud on --hud-log on
python3 bin/deadlock-mac game-fps --cap 60 --menu-cap 60 --apply
```

In the app, use **60 FPS + performance HUD** and **Set game and menu limits to
60 FPS**. The renderer request alone did not persist those in-game settings.

The verified display setup on our M2 Max's built-in display uses Retina borderless
at 3024×1964. With Steam/Wine still closed:

```sh
python3 bin/deadlock-mac retina --set on --apply
python3 bin/deadlock-mac graphics-preset --mode borderless --width 3024 --height 1964 --apply
```

These dimensions are specific to that display. Follow the
[Retina guide and rollback instructions](PERFORMANCE.md#experimental-high-resolution-borderless--retina)
for another display; external-monitor behavior remains untested. Fullscreen
1920×1200 still has coverage and focus failures on the tested Mac.

Configure the compatible Game Mode tool below, then use manager **Play** (CLI:
`launch --game-mode-tool /absolute/path/to/gamepolicyctl`). Confirm the HUD's
output dimensions and Game Mode On, and both in-game limits at 60. The user
verified these checks, screen coverage, pointer alignment and Command–Tab after
a full Steam restart. Gameplay performance at 3024×1964 has not yet been measured.

Connect to power and check Low Power Mode. Keep **Direct3D 11**: the paired DXMT
renders through Metal on the Apple GPU. Record the upscaler, render scale and
quality too; output dimensions alone do not establish internal rendering
resolution. Vulkan has not been tested with this setup.

## Automatic Game Mode during Play

First try Apple's native flow: while the game is in supported macOS fullscreen,
open Game Overlay with Command–Esc and enable Game Mode in its settings. In our
Wine test the overlay was unavailable, so we used Apple's developer tool instead.

Use a `gamepolicyctl` from a compatible Apple developer-tool installation. A full
Xcode installation is only relevant to obtaining that tool; it is not a
game runtime dependency. Xcode 15's copy crashes on the tested macOS 26, so merely
finding the filename is insufficient. The manager verifies Apple's signature,
then checks whether the tool can actually report status. It does not redistribute
or automatically download the binary.

In the app's **Game Mode** panel:

1. **Choose Apple tool…** if the selected Xcode's tool is absent or incompatible.
2. **Check Game Mode** to read the policy without changing it.
3. Leave **Enable during Play, then restore when Deadlock exits** checked.
4. Hit **Play**. Confirm **Game Mode On** in Deadlock's Metal HUD. You can close the
   manager; its detached watcher keeps running until the actual game process exits.
5. **Play session status** shows startup, game tracking and restoration. The
   original policy (`auto`, `on` or `off`) is restored on exit. An original `on`
   policy deliberately remains on afterward.

The equivalent source commands are:

```sh
python3 bin/deadlock-mac game-mode --tool /absolute/path/to/gamepolicyctl
python3 bin/deadlock-mac launch --game-mode-tool /absolute/path/to/gamepolicyctl
python3 bin/deadlock-mac game-mode --session
```

Omit the tool argument only if the selected Xcode supplies a compatible copy.
The app remembers your selection; source CLI invocations need the explicit argument
each time when the selected Xcode's copy is incompatible. If the tool cannot be
verified or enabled, Play reports the error before asking Steam to launch; it does
not silently claim Game Mode is working. Use `--without-game-mode` as the explicit fallback.

Normal Play has **no five-minute or other gameplay deadline**. A three-minute
startup timeout applies only while waiting for a game process: finish Steam's
login, download or update prompts, then press Play again. A per-user lock prevents
overlapping manager sessions across workspaces. Game Mode is a system-wide policy;
while active the watcher checks it and re-enables it if needed, then restores the
exact original policy at exit. It does not change Wine, Steam or game files.

If Wine holds a crashed process open in its debugger, close that error/debugger
dialog too. A minimized game is still running and keeps Game Mode on. **End session
and restore** explicitly cancels the override without killing the game or Steam:

```sh
python3 bin/deadlock-mac game-mode --stop-session
```

An uncatchable watcher kill, power loss or Apple-service failure can prevent cleanup.
After the game exits, use **Recover interrupted Play** or:

```sh
python3 bin/deadlock-mac game-mode --restore-session
```

Recovery uses the saved, signature-checked tool. The next Play also recovers an
interrupted session; if its game is still running in the same profile, it resumes
watching without losing the original policy. The private recovery receipt lives at
`~/Library/Application Support/Deadlock Manager/GameMode/session.json` so multiple
workspaces cannot unknowingly overwrite each other's state. Session logs stay in
the workspace's `DeadlockData/logs/<profile>`.

The separate **Timed diagnostic** section still offers a five-minute comparison
for an already running game launched without the automatic session. It requires
automatic policy and never overlaps a normal Play watcher. See
[diagnostics and recovery](PERFORMANCE.md#optional-game-mode-diagnostic).

Repeat Mina's bat ultimate in Hero Sandbox at unchanged graphics settings. Our
user reported around 60 FPS and the earlier stutter gone with Game Mode on; the
next acceptance step is a longer session and multiplayer, not another download.

## Updates and disk use

Steam updates itself and Deadlock through the existing account. Wine, DXMT and
support components use the versions and SHA-256 values in `config/runtime-lock.json`;
Python in the app uses `packaging/python-lock.json`. These are different update
channels. A Steam game patch can change compatibility without a manager update.

Use `runtime-verify` to compare installed components with their pinned archives,
and `doctor`/`runtime-dependencies` to inspect the setup. The current working set
is Highball Wine 20261006, paired DXMT a444716 and Sikarugir support 1.0.21. Do not
independently replace one of these with an arbitrary newer DLL.

The consolidated workspace uses one active Steam/game copy. Preserve shader caches
between performance comparisons. Keep backups and small diagnostic evidence; avoid
duplicating an entire game merely to rebuild the manager app. A truly fresh install
uses a new workspace; budget its disk use explicitly, verify it, then remove the
old copy only after preserving the data you need. Never relocate a live bottle.

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

## Exit, recover display settings, and verify hotfix status

Use **Exit Deadlock** in the app or `python3 bin/deadlock-mac exit`. This requests
normal closure and leaves Windows Steam available to sync. A Wine debugger or
unresponsive game is reported as a failure; it is not automatically force-killed.
Use `wine-hotfix` to inspect the verified overlay, or `wine-hotfix --set on/off`
with Steam closed. See [the build/rollback procedure](WINE-HOTFIX.md).

For display recovery with Steam closed, `graphics-preset` accepts `--mode borderless`
and explicit `--width` / `--height`, backs up the old configuration and preserves
quality/render scale. For example, this test Mac previously used 1512×982:

```sh
python3 bin/deadlock-mac graphics-preset --mode borderless --width 1512 --height 982 --apply
```

Choose dimensions appropriate to your display; this example is not universal.
Fullscreen 1920×1200 later showed a size mismatch/black-screen failure and remains
a qualification issue. Game Mode can still be enabled by manager Play in borderless.
