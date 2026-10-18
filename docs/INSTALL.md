# Installation, Steam and Game Mode

This is the canonical Deadlock setup guide. The maintained manager was merged to
`main` in [PR #1](https://github.com/shrav-k/deadlock-on-mac/pull/1).
No public player-ready app release is available yet. The separate Elden Ring
[research recipe](ELDEN-RING.md) is not enabled for gameplay.

## Choose your installation path

| Path | What you need | Sequence |
| --- | --- | --- |
| Built local app preview | Apple Silicon, macOS 15+, Rosetta 2, 80 GiB free | Select workspace → Set up Steam → Open Steam → sign in → Install Deadlock → Play |
| Source checkout | The same, plus Git, Python 3.12+ and Apple's Command Line Tools for media compilation | Clone the maintained branch, then run the commands below |
| Build an app yourself | Source prerequisites plus a compatible Swift compiler/macOS SDK | Follow [app packaging](../packaging/README.md), then use the app sequence |

Game Mode during Play is enabled by default and requires a compatible Apple-signed
`gamepolicyctl`. Setup discovers, validates and prepares it automatically. On a
fresh Mac without a compatible copy, install/update Xcode from Apple, open it once
to complete Apple's license and first-run setup, then retry
**Check Game Mode Setup**; no file picker or `xcode-select` change is required. To
play without that tool, turn off **Enable during Play** or use the CLI's
`bootstrap --without-game-mode` and `launch --without-game-mode`. The packaged app
can install and play without Xcode when this preference is explicitly off. On an existing
working installation, skip setup/download and use Open Steam → Play. Do not
bootstrap a running Wine environment.

Command Line Tools alone do not supply the required tool in the inspected 26.6
package. Keep compatible Xcode as the current default setup prerequisite; optional
non-macOS platforms and simulator runtimes are unnecessary for Game Mode setup.
Xcode **27.1 (27A9275)** on macOS **26.6.2 (25G83)** passed fresh packaged
dependency setup in an empty workspace on 2026-10-16, without an existing tool/cache.
Other Xcode/macOS pairs require the same check. See the [Game Mode setup decision](GAME-MODE-SETUP.md)
for evidence, the public native alternative and the remaining release gates.

## Steam fullscreen interface

In the manager's Play view, choose **Steam → Open Big Picture**, or run
`python3 bin/deadlock-mac steam --big-picture`. This opens the existing Windows
Steam account in Valve's fullscreen interface using `steam://open/gamepadui`. **Open Windows
Steam** keeps the normal desktop launch action; no persistent startup preference
is changed. **Exit Windows Steam** closes either interface through the same verified
shutdown path.

Big Picture's display selection is separate from the manager's Deadlock display
picker. Verify its monitor, coverage, pointer alignment and Command–Tab before
using it on a new display. This is an optional interface under qualification,
not a game performance setting. Continue using the manager's **Play** for its
automatic Game Mode session; starting games directly inside Steam does not start
that watcher. Opening Steam alone leaves the Game Mode policy unchanged.

Valve documents the startup-only `-gamepadui` flag in its
[Big Picture announcement](https://store.steampowered.com/news/posts/?enddate=1671645631&feed=steam_blog).
Neither that flag nor the legacy `steam://open/bigpicture` URI produced a mode
transition from an already-running desktop client in local testing. The current
`steam://open/gamepadui` URI did: Steam logged UIMode 4 and creation of its gamepad
interface. This URI also appears in
[Valve's client issue tracker](https://github.com/ValveSoftware/steam-for-linux/issues/12056).
Log transitions and clean process exit do not establish fullscreen coverage,
pointer alignment or focus recovery. In the first unlocked 0.4.6 check, the user
reported fullscreen on the MacBook and working clicks, but **Command–Tab failed**.
The LG remained the manager's prepared game target; Steam did not follow that
selection. Keep Big Picture optional until focus recovery and monitor placement
pass. See the [qualification record](COMPATIBILITY.md#046-big-picture-focus-failure--2026-10-16).

## Source installation

Requirements: Apple Silicon, macOS 15 or newer, Rosetta 2, Python 3.12 or newer,
Apple's Command Line Tools for the source-build path,
and at least 80 GiB free. Current runtime testing is on an M2 Max with macOS 26.6.2.
Older supported OS versions are not yet tested here. Use macOS's normal Rosetta
installation flow if needed; this manager does not silently accept its license.

Clone this repo inside `Projects/Games/Deadlock`:

```sh
mkdir -p ~/Projects/Games/Deadlock
cd ~/Projects/Games/Deadlock
git clone https://github.com/shrav-k/deadlock-on-mac.git
cd deadlock-on-mac
python3 bin/deadlock-mac runtime-install --runtime highball
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer python3 packaging/build_wine_hotfix.py \
  --workspace "$PWD/.." --build-dir "$PWD/../Tools/wine-hotfix-build"
python3 bin/deadlock-mac bootstrap
python3 bin/deadlock-mac steam
```

`bootstrap` checks the Mac, disk space, Rosetta and the selected Game Mode prerequisite,
then combines runtime installation,
profile creation and Steam setup. The lower-level `runtime-install`, `profile-create`
and `setup` commands remain available. Runtime installation fetches the pinned Highball Wine engine and paired DXMT build,
plus Sikarugir support libraries and matching [FFmpeg libraries](MEDIA-RUNTIME.md),
checks their hashes, and extracts them under `../Runtimes`. `setup` initializes
`../Bottles/highball` and installs the official Windows Steam client. Downloads, state,
game files and backups stay outside this repository. macOS/Wine can still create
ordinary per-user caches and preferences outside Games.

The source sequence explicitly builds the pinned startup/exit fixes before Steam
setup. The [hotfix guide](WINE-HOTFIX.md) covers build verification and rollback;
do not repeat the build into an existing directory. A packaged preview containing
these verified payloads needs no player-side compiler for this step.

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
Steam and all Wine apps. Remove the extra renderer cap and save the game's
actual game/menu limits:

```sh
python3 bin/deadlock-mac performance --fps-cap 0 --hud on --hud-log on
python3 bin/deadlock-mac game-fps --cap 60 --menu-cap 60 --apply
```

In Diagnostics, use **Enable Metal HUD logging (game controls FPS)**. In Settings,
use **Set game and menu limits to 60 FPS**. DXMT's optional pacing cap must divide the monitor's
refresh rate; requesting 60 on our 144 Hz LG produced 48 FPS. The game cap avoids
that extra renderer constraint. Verify both limits in the game.

Optional [visual testing](VISUAL-TESTING.md) provides window screenshots and scoped
input. macOS Screen Recording and Accessibility permissions require the user;
installation does not grant them automatically.

The previously verified display setup on our M2 Max's built-in display uses Retina
borderless at 3024×1964. Use the display picker rather than hardcoding that size
for another Mac. With Steam/Wine still closed:

```sh
python3 bin/deadlock-mac display
python3 bin/deadlock-mac display --prepare default --retina auto
```

`default` selects the macOS main display. For a secondary monitor use its identity
from `display`, or `external` when exactly one external screen is connected. The
manager does not change which macOS display is main. See the policy below and
[external-display acceptance status](EXTERNAL-DISPLAYS.md). Exclusive fullscreen
1920×1200 still has coverage and focus failures on the tested Mac.

Complete Game Mode setup below, then use manager **Play** (CLI: `launch`). Confirm the HUD's
output dimensions and Game Mode On, and both in-game limits at 60. The user
verified these checks, screen coverage, pointer alignment and Command–Tab after
a full Steam restart. Gameplay performance at 3024×1964 has not yet been measured.

Connect to power and check Low Power Mode. Keep **Direct3D 11**: the paired DXMT
renders through Metal on the Apple GPU. Record the upscaler, render scale and
quality too; output dimensions alone do not establish internal rendering
resolution. Vulkan has not been tested with this setup.

## Display and Game Mode launch policy

Keep **Enable during Play and restore on exit** checked on both laptop and external
displays. Our earlier Mina test improved with Game Mode enabled; that is local
evidence, not a guarantee for every game or monitor. Apple describes Game Mode as
prioritizing game CPU/GPU access and reducing background use. Its normal automatic
path requires supported macOS fullscreen, which a Wine borderless window does not
necessarily provide. The manager's developer-tool override is system-wide and does
not prove native per-game eligibility. [Apple Game Mode](https://support.apple.com/en-us/105118)

| Target / activity | Manager policy |
| --- | --- |
| Built-in Retina display, currently 2× | Automatic Retina on; at the recorded desktop mode request 3024×1964 borderless output |
| LG ULTRAGEAR, currently 1× | Automatic Retina off; at its recorded desktop mode request 2560×1440 borderless output |
| Another external display | Resolve its native backing scale; a high-DPI external display may need Retina on |
| Play through the manager | Save the current Game Mode policy, enable it for startup and the actual game lifetime, then restore the saved policy |
| Steam alone / display test grid | Do not change Game Mode policy |
| Command–Tab / Quit Manager while playing | Keep the detached Play watcher running; restore on actual game exit |
| Game Mode preference unchecked | Leave system policy unchanged on the next launch; this does not force Game Mode off or cancel an existing watcher |

In **Settings → Display**, choose **Play on** and **Automatic — match selected
display**, close Windows Steam, then **Apply Display**. The manager backs up the
affected settings, applies Wine's bottle-wide Retina option, checks guest monitor
mapping and saves borderless output. No per-monitor DPI support is implied. Keep
manual On/Off overrides for diagnostics. See the [Retina source findings](WINE-PRACTICES.md#why-these-dimensions-appear).

The Play screen shows the **prepared** display, output and Retina state. Its Game
Mode line describes the launch preference, not a live policy measurement. Read
**Diagnostics → Game Mode Status** and **Play Session Status** for that evidence.
Unapplied UI choices block Play rather than silently using the old choice. Apply
Display refreshes the saved summary. Play also validates the actual connected
layout, settings and Wine mapping; stale or disconnected selections require
preparation again. It does not silently stop Steam, select a fallback screen or
change resolution during play. After changing desks, quit the game/Windows Steam,
refresh, choose the connected screen and apply before the next Play.

Retina configuration remains saved for subsequent Steam sessions. Game Mode is
temporary: restore the exact previous policy, including `on` if that was already
set. A failed startup also restores it. Native resolution and internal render
scale are separate; the output setting alone does not establish GPU workload.

For built-in acceptance, start with Automatic Retina and compare the **Win32
borderless popup** grid with **SDL fullscreen desktop**. For each, record all four
edges, corner clicks, Command–Tab, menu-bar behavior, requested/backbuffer dimensions
and normal closure. The manager leaves Game Mode policy unchanged during grids.
Then check the game menu through Play and Exit, including Game Mode restoration;
this is not gameplay qualification. A Retina-off comparison is an explicitly
labelled diagnostic and should be followed by restoring Automatic. External
display and actual gameplay acceptance remain separate pending runs.

## Automatic Game Mode during Play

Apple's native flow uses an eligible game in macOS fullscreen and needs no player
Xcode installation. In our Wine test the overlay was unavailable, so the manager
currently uses Apple's developer tool instead. Adding game metadata to the manager
alone does not transfer eligibility to the Steam/Wine child. Native integration
remains unqualified; see the [research and installation policy](GAME-MODE-SETUP.md).

Use a `gamepolicyctl` from a compatible Apple developer-tool installation. A full
Xcode installation is only relevant to obtaining that tool; it is not a
game runtime dependency. Xcode 15's copy crashes on the tested macOS 26, so merely
finding the filename is insufficient. The manager verifies Apple's signature,
then checks whether the tool can actually report status. Discovery checks a
prepared copy, the earlier workspace tool, selected Xcode and Xcode bundles in
`/Applications` or `~/Applications`, skipping incompatible copies. Setup preserves
a verified copy under `DeadlockData/tools/game-mode/<digest>/gamepolicyctl` and
checks it again after OS updates. It does not redistribute or download Apple's
binary. Apple's daemon rejected our unentitled native probe, so a custom helper
is not a supported substitute for this prerequisite.

In the app's **Game Mode** panel:

1. **Check Game Mode Setup** to discover, validate and prepare the tool. Set Up
   Steam also performs this check before downloading runtimes or starting Wine.
2. If unavailable, use **Get Xcode from Apple**, install a compatible release and
   check again. **Advanced tool override** is optional; **Use Automatic** clears
   an old manual choice. Setup does not change the Game Mode policy.
3. Leave **Enable during Play, then restore when Deadlock exits** checked.
4. Hit **Play**. Confirm **Game Mode On** in Deadlock's Metal HUD. You can close the
   manager; its detached watcher keeps running until the actual game process exits.
5. **Play session status** shows startup, game tracking and restoration. The
   original policy (`auto`, `on` or `off`) is restored on exit. An original `on`
   policy deliberately remains on afterward.

The equivalent source commands are:

```sh
python3 bin/deadlock-mac game-mode --prepare
python3 bin/deadlock-mac launch
python3 bin/deadlock-mac game-mode --session
```

Normal CLI/app launches use automatic discovery. Advanced `--tool` or
`--game-mode-tool` overrides remain available. A new Play session prepares its
verified copy before changing policy, so moving Xcode does not remove the worker's
recovery tool. An active/interrupted session still uses its recorded tool. If it cannot be
verified or enabled, Play reports the error before asking Steam to launch; it does
not silently claim Game Mode is working. Use `--without-game-mode` as the explicit fallback.
For setup without forced Game Mode, uncheck **Enable during Play** before **Set Up
Steam**, or use `bootstrap --without-game-mode`. Missing Xcode never silently
changes that preference. Fully automatic forced Game Mode on a Mac with no Apple
tool remains unavailable; this dependency is an explicit setup prerequisite.

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
Steam's non-forced app stop, verifies the game process has ended and waits for the
previous Game Mode policy to be restored. It leaves Windows Steam available to
sync. The earlier Wine close-window message could be accepted without the game
exiting; the manager no longer uses that path. A Wine debugger or
unresponsive game is reported as a failure; it is not automatically force-killed.

Use **Exit Windows Steam** or `python3 bin/deadlock-mac steam-exit` to close
Deadlock first, then ask that profile's Windows Steam to shut down normally.
The manager waits for Steam and its helpers; it does not dismiss sync/download
prompts or affect native Mac Steam. A failed game exit stops the Steam-shutdown
sequence so the error remains visible. Repeating either command after closure
does not reopen Steam or Deadlock.

If only an orphaned Steam overlay remains after its game, Steam client, browser
and service have exited, the manager waits five seconds and rechecks ownership
before stopping that helper with SIGTERM. Details explicitly report this recovery;
it is not a normal overlay exit. No game/client, other bottle or Wine server is
terminated, and there is no SIGKILL escalation.

**Quit Manager**, Command–Q, and closing the manager's window exit only the
manager. Steam/game stay running and the detached watcher still restores Game
Mode on game exit. If an operation is active, quitting waits for it to finish;
a timed Game Mode diagnostic is stopped and restored first. An operation failure
keeps the manager open for recovery. The app remembers the workspace, profile
and chosen Apple tool across launches.

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
