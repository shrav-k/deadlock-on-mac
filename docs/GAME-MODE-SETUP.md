# Game Mode setup and distribution decision

Research and setup qualification date: 2026-10-16. The setup checks below did not
launch Steam or gameplay; the user subsequently authorized live testing.

Keep automatic Game Mode enabled by default. For the current developer preview,
retain a compatible Apple `gamepolicyctl` as an explicit prerequisite, obtained
from the user's official Xcode installation. Do not trade away the observed
performance benefit simply to reduce installation size. This is a provisional
deployment choice. Xcode 27.1 on macOS 26.6.2 passed the fresh dependency check
below; additional OS/tool versions require their own qualification.

## What Apple supports

Game Mode itself does not require Xcode on a player's Mac. Apple documents
automatic activation for eligible games using **native macOS fullscreen** on
Apple Silicon with macOS 14 or newer. A Windows fullscreen setting or a
screen-sized borderless Wine window does not by itself prove eligibility.
[Apple's player requirements](https://support.apple.com/en-us/105118)

Apple's current developer guidance uses `LSSupportsGameMode = true` in the game's
Info.plist; the key's documented macOS availability starts at 26. Earlier Apple
guidance identifies games using `LSApplicationCategoryType = public.app-category.games`
and requires fullscreen/frontmost operation. These describe eligibility, not a
public API for forcing system policy throughout an arbitrary child process's life.
[Game Mode adoption](https://developer.apple.com/videos/play/wwdc2025/209/),
[key documentation](https://developer.apple.com/documentation/bundleresources/information-property-list/lssupportsgamemode),
[Apple framework engineer's guidance](https://developer.apple.com/forums/thread/739387)

Apple DTS explicitly says Info.plist properties are not inherited by child
processes. Metadata must belong to the relevant executable's bundle or embedded
Info.plist; placing it only on our SwiftUI manager is insufficient. A separate
DTS reply cautions that Game Mode does not simply migrate from a launcher to a
child's game window. Applying this to our Steam/Wine launch chain is an engineering
inference that requires testing, not an Apple guarantee of Wine support.
[Metadata inheritance](https://developer.apple.com/forums/thread/787774),
[launcher/child-window discussion](https://developer.apple.com/forums/thread/787702)

## Package findings

| Option | Evidence | Current decision |
| --- | --- | --- |
| Native Game Mode integration | Public Apple documentation; no player Xcode requirement | Preferred long-term route, not yet qualified for our Wine/Steam host |
| Command Line Tools alone | Installed package 26.6.0.0.1781586589 and its file receipt contain no `gamepolicyctl` | Insufficient for the current override; do not recommend `xcode-select --install` as its fix |
| Full Xcode | Xcode 15's copy failed on macOS 26.6.2; official Xcode 27.1 passed uncached preparation on that OS | Qualified dependency pair; retain signature/status checks and repeat after updates |
| Additional Tools / Game Porting Toolkit | No standalone supported `gamepolicyctl` distribution was established by this research; authenticated download payloads were not exhaustively inspected | Do not promise these as smaller replacements |
| A copied binary or custom helper | Existing Apple-signed tool works locally; an unentitled helper was rejected | Local evidence is not a redistributable dependency or a public API contract |

Apple describes Command Line Tools as a subset and notes that some tools require
full Xcode. The absence finding above is specific to the inspected package.
[Command Line Tools documentation](https://developer.apple.com/documentation/xcode/installing-the-command-line-tools)

The working local tool links Apple's private GamePolicy framework and carries
privileged GamePolicy XPC entitlements. Our signature/status checks validate the
binary and immediate compatibility; they do not establish a supported third-party
API, permission to redistribute it, or compatibility with future macOS releases.
Installing Xcode does not make our Wine override an Apple-supported game integration.

## Installation policy

1. Obtain Xcode from Apple's official distribution, selecting a release compatible
   with the installed macOS. Complete Apple's first-run setup and license flow.
   A paid Developer Program membership is not required for tool downloads.
   [Xcode downloads](https://developer.apple.com/xcode/resources/),
   [system requirements](https://developer.apple.com/xcode/system-requirements)
2. Keep the macOS components needed for this project. Other platform support and
   simulator runtimes can be omitted; Apple provides component management in
   Xcode Settings. Do not require the optional Metal build toolchain solely for
   Game Mode without evidence that it is needed.
   [Manage Xcode components](https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components)
3. Use **Check Game Mode Setup**. The manager discovers Xcode, validates Apple's
   signature, probes status and prepares its recovery copy. It does not require
   changing the global `xcode-select` selection or manually locating the tool.
4. Retain the current Play watcher: enable for the actual game lifetime, without
   a play-time limit, then restore the exact prior policy. Keep failure explicit.
   An opt-out is a diagnostic alternative, not the qualified performance preset.

Xcode installation alone does not improve game performance. The relevant outcome
is verified Game Mode activation and measured gameplay behavior. Developer
profiling tools are useful separately, but are not proof of faster play.

## Qualification before removing or finalizing the prerequisite

- Test official Xcode acquisition on a clean workspace with no legacy tool,
  override or prepared cache. Record macOS, Xcode build, tool hash/signature and
  status result. Repeat after OS/tool updates; reject incompatible tools early.
- For a future native backend, first test an owned native fullscreen app, then
  the actual Wine host and Steam-launched game menu. Use our own bundle identity;
  verify the game receives Game Mode, not just the launcher.
- Cover native fullscreen, Retina scaling, pointer alignment, Command–Tab,
  secondary display placement and disconnects. Native eligibility follows macOS
  foreground/fullscreen policy; do not claim it preserves the override's exact
  always-on-until-exit behavior without checking those transitions.
- Retain automated missing/incompatible-tool, discovery, cache, lifecycle and
  restoration tests. Integration acceptance must verify real status/HUD and clean
  exit, not infer Game Mode from a successful subprocess return alone.
- Keep performance claims separate from setup checks. Resume gameplay and
  external-display performance measurements only when the user requests them.

The initial research decision changed documentation only; the subsequent
installation and qualification work is recorded below. Native activation remains
unimplemented.

## Installation qualification follow-up — 2026-10-16

The user subsequently authorized replacing local Xcode. The Mac App Store updated
`/Applications/Xcode.app` from 15.0 to **27.1 (27A9275)** on macOS **26.6.2 (25G83)**.
Deep/strict bundle verification passed and Gatekeeper identified an accepted Mac
App Store installation. Its `gamepolicyctl` passed the existing Apple signature
requirement; SHA-256:
`9a1394ceffd5ca340e026dd020c496a7d14dd333187986dae6bfc1e3ed5d40e5`.

**Fresh packaged dependency setup passed.** The user reviewed and authorized
accepting Apple's agreement. Required system components installed; optional
platform/simulator downloads were deselected. Both the license check and
`xcodebuild -checkFirstLaunchStatus` returned zero. The packaged manager's own
Python and modules installed/verified FFmpeg and discovered the new Xcode tool
in an empty temporary workspace. Source path and hash matched the bundle above;
repeat preparation selected the new cache. Game Mode stayed Off with policy
`auto` throughout. No Steam or gameplay ran as part of this qualification.

The new `packaging/check_onboarding.py --require-xcode /Applications/Xcode.app`
mode checks Xcode identity/signature and first-run readiness, then requires
uncached automatic discovery from that exact installation. It records source and
digest, verifies repeat preparation and checks unchanged policy. A supplied tool
fixture cannot satisfy strict qualification. All **188 automated tests** pass,
including missing/incompatible tools, legacy/cache rejection, incomplete first
launch and signature failures. See [the qualification command](../packaging/README.md#qualify-a-fresh-xcode-prerequisite).

Swift 6.4 compiled the actual manager source with the new SDK. All 13 native
AppKit lifecycle scenarios, display-model checks and activation-policy checks
passed. The existing workspace now uses the new prepared tool and automatic
discovery; its old manual override was removed. Older recovery copies were
preserved. The private evidence is `DeadlockData/qualification/fresh-xcode-27.1.json`
and `xcode-27.1-native-tests.log`.

This qualifies dependency preparation on this Mac, not a full clean-machine
Steam installation, native Wine Game Mode eligibility, or gameplay performance.
The Apple tool still uses private framework interfaces; a compatible Xcode install
does not turn that override into a supported public integration API.
