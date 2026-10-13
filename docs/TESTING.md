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
