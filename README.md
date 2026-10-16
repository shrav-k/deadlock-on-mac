# Deadlock on Mac — Steam-first, free-runtime workbench

Run Valve's **Windows Steam client with your existing Steam account**, then install
and launch Deadlock from that library. This maintained fork aims to make a durable
unpaid setup easy to test, diagnose and update.

**Status: experimental. Gameplay has been observed, but startup/exit faults and
sustained performance remain under investigation.**
See the [compatibility ledger](docs/COMPATIBILITY.md) for observed results rather
than inferred compatibility.

The default free candidate is **Highball's Wine 11 build + its paired DXMT build**.
Steam login, installation, restart and a Direct3D rendering probe work on our M2 Max.
The clean installation also reached Deadlock's menu after a failed first launch.
A local macOS app preview can install Steam without a player-supplied Python.
A Sikarugir Wine 11 + upstream DXMT 0.80 pair remains available for
comparison, with a known black Steam login window on this Mac. Official
CrossOver is an optional comparison provider; the project does not depend on a
CrossOver trial. Every profile owns a separate Steam environment so runtime
experiments preserve the existing setup.

## Start here

Use the [complete installation and Game Mode guide](docs/INSTALL.md). **This work
is currently on `maintain/free-steam-runtime-manager`; the fork's default `main`
branch still contains the original installer.** Clone the maintained branch:

```sh
mkdir -p ~/Projects/Games/Deadlock
cd ~/Projects/Games/Deadlock
git clone --branch maintain/free-steam-runtime-manager https://github.com/shrav-k/deadlock-on-mac.git
cd deadlock-on-mac
```

Place the repository inside `Projects/Games/Deadlock`. Requires Apple Silicon, macOS 15+,
Rosetta 2 and Python 3.12+. Source setup also needs Apple's Command Line Tools to
build pinned media libraries. Default Game Mode requires a compatible Apple tool
from Xcode; setup discovers and validates it automatically. The packaged app
includes the media payload and needs no compiler. Review [security boundaries](SECURITY.md), then:

```sh
python3 bin/deadlock-mac bootstrap
python3 bin/deadlock-mac steam
```

Sign into **your existing account in Steam**. Then install and play:

```sh
python3 bin/deadlock-mac install
python3 bin/deadlock-mac launch
python3 bin/deadlock-mac doctor
python3 bin/deadlock-mac exit
python3 bin/deadlock-mac steam-exit
```

Steam manages game downloads, updates, entitlement, friends and any supported
Cloud files. The manager never launches `deadlock.exe` directly or reads your
credentials. Deadlock's public listing does not currently advertise Steam Cloud;
verify the in-client options and keep local backups instead of assuming all
settings sync. [Installation and account guide](docs/INSTALL.md)

The [native app preview](packaging/README.md) bundles Python and calls the same
manager modules. It is currently a local development build, not a notarized download.
For controlled performance tests, see the [60 FPS baseline guide](docs/PERFORMANCE.md).
Play enables Game Mode using a compatible Apple developer tool, keeps it on for
the game process's lifetime with **no play-time limit**, then restores the prior
policy. **Check Game Mode Setup** prepares a verified local copy automatically;
it reports a missing/incompatible Xcode prerequisite before Steam setup. See the
installation guide for recovery and the explicit option to set up/play without it.

The previously verified M2 Max built-in-display baseline is **Retina, 3024×1964 borderless,
Direct3D 11, Game Mode On, and game/menu limits of 60 FPS**. The user verified
screen coverage, pointer alignment, Command–Tab and those settings after a full
Steam restart. Gameplay performance at this resolution remains unmeasured;
1920×1200 fullscreen still has coverage/focus failures. See the baseline guide
before applying display-specific settings.

The preview includes a **Play on** display picker. Close Windows Steam, click
**Refresh displays**, select the monitor and **Prepare display**. The manager
preserves macOS's main display and checks the selection again before Play. A
changed or disconnected display requires preparation again; it never silently
chooses a different screen. Use **Test grid** and the game menu to verify scaling
and input before gameplay. The 0.3.1 grid stays open until Escape or **Stop Grid**;
launch it from the manager to exercise the new native activation handoff. The
initial LG game window was not visible to the user, so secondary-display support
is still under validation. See [display setup and limits](docs/EXTERNAL-DISPLAYS.md).

## Layout

```text
Projects/Games/Deadlock/
  deadlock-on-mac/    source, tests and documentation only
  Downloads/          verified runtime and Steam installers
  Runtimes/           active engines, renderers, media/support libraries and hotfixes
  Bottles/            one Windows Steam environment per profile
  DeadlockData/       profiles, prepared Apple tool, logs and research evidence
  DeadlockBackups/    local Deadlock data snapshots
  Tools/              legacy local tool; temporary developer builds
  Builds/             one current app, one Previous rollback, small build history
```

See [workspace ownership and cleanup](docs/WORKSPACE.md) for what must stay, what
can be regenerated, and how to keep future experiments from accumulating here.
This is a development workspace, not the directory tree a player must download.
The app installs its runtime components separately; it never ships this workspace.

No administrator privileges, native Steam modifications, trial resets, automatic
Cloud-conflict choices, or global process kills. Wine is not a security sandbox.
The manager has no third-party Python dependencies.

## Develop and compare

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 bin/deadlock-mac profiles
python3 bin/deadlock-mac runtimes
python3 bin/deadlock-mac launch --dry-run
python3 bin/deadlock-mac runtime-verify
python3 bin/deadlock-mac runtime-dependencies
```

- [Runtime research, alternatives and upgrades](docs/RUNTIMES.md)
- [GitHub project review and reusable engineering findings](docs/GITHUB-RESEARCH.md)
- [Autonomous qualification and optimization plan](docs/AUTONOMOUS-TESTING.md)
- [Matching FFmpeg libraries, packaging and automated media probes](docs/MEDIA-RUNTIME.md)
- [External displays, hotdesking and performance research](docs/EXTERNAL-DISPLAYS.md)
- [Wine/CodeWeavers practices and secondary-display investigation](docs/WINE-PRACTICES.md)
- [Module boundaries, packaging plan and release gates](docs/ARCHITECTURE.md)
- [Deployment readiness and future game recipes](docs/ARCHITECTURE.md#deployment-readiness--2026-10-16)
- [Tests, gameplay acceptance and performance comparisons](docs/TESTING.md)
- [Observed compatibility](docs/COMPATIBILITY.md)
- [Security and provenance limitations](SECURITY.md)
- [Changes from upstream](CHANGELOG.md)

Manager source code is MIT licensed. Runtime components have their own licenses;
the app carries a source-inclusive FFmpeg payload and downloads the main runtime
components separately. This project is not affiliated with Valve, Apple,
CodeWeavers, WineHQ or Sikarugir. Original upstream attribution is retained in
[LICENSE](LICENSE) and Git history.

The [quality protocol](docs/QUALITY.md) defines runtime promotion gates, repeated
sandbox comparisons and real-match recording. The [Wine exit hotfix guide](docs/WINE-HOTFIX.md)
covers the pinned source build, regression probes and reversible activation.
**Exit Deadlock** asks Steam to stop the game normally and verifies actual exit and
Game Mode restoration. **Exit Windows Steam** then shuts down that profile's client
and waits for its helpers. **Quit Manager** (also Command–Q or closing its window)
leaves Steam/game running and keeps the detached Game Mode watcher active. A crash,
timeout or pending restoration is reported as a failure rather than a successful exit.
