# Testing and acceptance

Run the dependency-free suite:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Unit tests use temporary directories and fake process launches. They cover archive
path traversal and links, corrupted cached downloads, atomic-write failure,
concurrent state writers, profile/prefix separation, shell metacharacters in paths,
environment credential leakage, Steam-only launches, malformed Valve manifests,
CrossOver signature rejection, backup exclusions, live-setup refusal, reversible
performance/display settings and per-process/time-bounded telemetry. CI also
type-checks the native app source. CI never signs into Steam,
installs a game or downloads runtime binaries.

## Native graphics probe

`tests/native/d3d11_probe.c` creates a window, hardware D3D11 device, render target
and swapchain, then clears and presents 120 frames. It has no Steam dependency.
Compile with an existing Windows cross-compiler; for example:

```sh
x86_64-w64-mingw32-clang -O2 -Wall -Wextra tests/native/d3d11_probe.c \
  -ld3d11 -ldxgi -ldxguid -luser32 -o /path/to/private/d3d11-probe.exe
```

Run it with the selected profile's Wine and the environment returned by
`deadlock_mac.runtime.environment(profile)`. Keep its log in private test data.
The tested compiler was the official LLVM-MinGW 20261006 macOS universal build,
archive SHA-256 `a7a19b11048e89372637d26279cdb7c430ed3cf8c1e224310421312bf986ebf6`.
Source: [LLVM-MinGW release](https://github.com/mstorsjo/llvm-mingw/releases/tag/20261006).
It is optional developer tooling, not a player installation requirement.

## Live acceptance gate

Record each step separately. An automated launcher returning a PID proves only
that the request was submitted.

- Runtime can initialize a fresh prefix and run a small Windows command.
- Current Windows Steam opens and self-updates without patches to its updater.
- The user signs into their existing account using Valve's own login UI.
- Deadlock downloads and updates through that Steam library; record app build ID.
- Steam launches Deadlock, and renderer logs confirm the intended graphics backend.
- Menu and training/sandbox render correctly; input and audio work.
- Existing account data is present. Check which settings have Cloud support, whether
  sync finishes, and what must be protected with a local backup.
- User tests a friend invite, party, voice if wanted, and a complete match.
- Exit normally, finish syncing, restart Steam and relaunch successfully.
- Back up game data with Steam/Wine closed, verify archive hashes, and test recovery
  in a disposable copy before claiming restore coverage.

Do not send friend invites or join public matches automatically. The user handles
Steam Guard, credentials and social/gameplay interactions.

## Compare runtime performance

Use one runtime at a time, the same account/game build, plugged-in power, identical
resolution, graphics settings, FPS cap and map/replay. Allow shader warm-up. Record
median FPS, lows/frame-time spikes, freezes, visual defects and memory. Repeating a
controlled training sequence is more useful than comparing two unrelated matches.

Record both the requested backend and evidence of the loaded backend. Do not infer
success merely from an environment variable or from seeing a game process. A result
on M4 hardware is not an M2 Max result, and a successful match is not a promise that
a future game/anti-cheat update will work.

See [performance testing](PERFORMANCE.md) for the 60 FPS launch settings, shader
warm-up, output-versus-render resolution and the limits of Metal HUD samples.

## Runtime qualification and exit regression

Use [QUALITY.md](QUALITY.md) for the full promotion matrix and marked match
measurement commands. `packaging/check_runtime.py` builds and executes both
architectures of `tests/native/device_notify_probe.c`, checking exact Windows
error codes and valid-handle cleanup. `--graphics` also runs the existing rendering
probe. [WINE-HOTFIX.md](WINE-HOTFIX.md) documents the pinned source backport.

The manager suite additionally covers Steam app-stop requests, actual process exit,
pending/failed restoration, missing clients, changed/reused PIDs, profile isolation,
Steam helper shutdown, timeouts, idempotence, hotfix corruption/rollback, and
benchmark log rotation, PID filtering and metadata privacy. Packaging tests inject
build failures and concurrent outputs to verify incomplete apps are not published.
macOS CI compiles/runs `tests/native/manager_lifecycle_test.swift` against the same
quit policy used by the UI (idle, active operation, failure and diagnostic cleanup).
On macOS 15+, `python3 packaging/check_manager_app.py` additionally builds an
isolated test app with the real AppKit delegate, window, SwiftUI content, model and
process runner. Its fake CLI exercises the actual close button and application
quit action during successful, failed and cancelled operations, including a quit
before the diagnostic worker is registered. It checks that cleanup completes
before termination, failures keep the manager available, and asynchronous
completion does not stall. It never opens Steam or starts gameplay. These native
integration tests run in a separate macOS 15 CI job; policy tests alone did not
catch the 0.2.0 SwiftUI window ownership regression.
Native Wine probes are opt-in local checks, not run by credential-free unit CI.

## Menu-only lifecycle checks (no gameplay)

With an installed, signed-in profile and Deadlock closed:

```sh
python3 packaging/check_lifecycle.py --workspace .. \
  --game-mode-tool /absolute/path/to/gamepolicyctl \
  --manager-app '../Builds/Deadlock Manager.app' --cycles 5
```

This explicitly launches Deadlock through Steam, waits briefly without sending
input, then tests Exit Deadlock, Game Mode restoration, Steam remaining open,
Exit Windows Steam and repeated no-op exits. Every cycle starts Steam cold.
Omit `--manager-app` to test the source CLI. It neither enters a sandbox/match nor
changes display/performance settings. Private reports/logs live under
`DeadlockData/lifecycle-checks/`. A failure stops the run and attempts only normal
game closure; no force-kill or automatic prompt confirmation is used. A process
surviving startup is not proof of correct visuals or gameplay compatibility.

## Steam-only restart and shutdown checks

After a Steam client update, isolate client lifecycle from game behavior:

```sh
python3 packaging/check_lifecycle.py --workspace .. \
  --game-mode-tool /absolute/path/to/gamepolicyctl \
  --manager-app '../Builds/Deadlock Manager.app' \
  --steam-only --idle-seconds 180 --cycles 3
```

This opens Steam, waits for client/browser processes, allows the chosen idle
interval, requests normal shutdown, checks the unchanged Game Mode policy and
tests a repeated no-op shutdown. It never launches Deadlock. An existing Steam
client can be used for the first cycle; later cycles start after verified client
shutdown. Process presence is not a login or UI acceptance check. If the user
starts Deadlock, the harness stops without closing it. A failed shutdown stops
the test and preserves evidence; it never escalates to force termination.

Actual buttons, Command–Q and red-close still need UI acceptance. A cold restart
recovering a hung client does not establish that its underlying hang is fixed.
