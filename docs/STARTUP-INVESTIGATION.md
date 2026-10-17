# Built-in Retina startup investigation

2026-10-16, M2 Max, macOS 26.6.2, Highball Wine 20261006, DXMT a444716,
Steam client 1791918634, Deadlock build 25997478. Both displays remained connected;
the built-in display remained the macOS main display. No new game download,
account change, Steam beta switch or renderer/synchronization change was made.

## Findings

The earlier built-in launch failures contain Steam's `BMainLoop` stall and
`fatal stalled cross-thread pipe` messages before Deadlock starts. **The reproduced
stall is in legacy WinMM audio enumeration, not a Retina-only launch path.** The same
main-loop warning also occurred in an LG launch that eventually succeeded.
Do not equate that warning alone with a fatal launch or a display defect.

The actual 0.4.4 Play button later reproduced a complete startup timeout on the
LG with Retina Off. The manager displayed the delayed error and restored `auto`;
its Exit Windows Steam and Quit Manager buttons then completed. This rules out
Retina On as a necessary condition. A separate `-silent -applaunch` candidate
also timed out, so it has not replaced the normal Steam protocol launch.

Both captured failures show `IPC:CSteamEngine` inside `winecoreaudio.so` /
`AudioUnitSetProperty` across their five-second samples. The original sample also
contains `AudioDeviceCreateIOProcID`. This is a stronger audio-enumeration lead
than the generic CEF warning. Soju documents the same assertion during legacy
WinMM format probing, and the matched local Wine source still contains that loop.
Wine's [format-probing removal](https://github.com/wine-mirror/wine/commit/c3a1bc86134bd6ae4bd781f6ae79f98122ba5e98)
depends on its AUTOCONVERTPCM behavior; the candidate includes all four prerequisites
and regression probes. No audio-driver disabling workaround is promoted.
Private samples: `lg-stall-steam.sample.txt` and
`silent-stall-steam.sample.txt` under this qualification folder.

The reversible Steam-only audio diagnostic launched in 30.06s and closed normally.
After its registry value was deleted and absence verified, the normal-audio
control timed out again. Steam had already exited during the control's sample;
that incomplete sample is not additional stack evidence.

`tests/native/winmm_probe.c` isolates the issue without Steam or Deadlock: original
WinMM did not complete device enumeration before the 45-second watchdog. With the
matched upstream series, enumeration completed in 592ms (x86_64) and 584ms (i386).
Both architectures passed 20 PCM, two floating-point and one mu-law silent
playback/completion checks, valid mixer open/close and invalid-format rejection.
This verifies conversion/control flow, not audible quality or microphone capture.
Two independent builds produced identical WinMM bytes. The unchanged sechost
overlay also reproduced with the new toolchain. Export lists match the installed
engine. Steam's memory map confirms the candidate WinMM and original exit-fix
sechost were both loaded during the live candidate run.

The current investigation reached a running game with Retina On and prepared
3024×1964 output via source CLI, packaged CLI and the actual manager Play button.
The source and packaged Python modules were byte-identical; Python interpreters
were 3.13.2 and 3.13.16 respectively. Both routes succeeded, so interpreter
version alone does not explain the prior failures. Prepared output and process
existence are not proof of visible coverage or pointer alignment.

| Case | Result | Private evidence |
| --- | --- | --- |
| Source CLI, built-in Retina On | Game process and PID-specific Metal HUD samples; normal game exit | `qualification/20261016-retina-hang/builtin-source-result.json` |
| Packaged CLI, built-in Retina On | Startup 29.08s; game/Steam/Wine exit and exact Game Mode restoration passed | `lifecycle-checks/20261016T225926748356Z/report.json` |
| Repeated packaged built-in cycles | Starts at 26.93s and 28.98s; both games exited, policy restored; second Steam shutdown failed because of an orphan overlay; third cycle not run | `lifecycle-checks/20261016T230243345920Z/report.json` |
| Actual manager buttons, built-in Retina On | Play created the game; Exit Deadlock and Exit Windows Steam completed; manager Quit closed the app | `qualification/20261016-retina-hang/manager-button-start.json` plus launch/exit logs |
| Packaged LG, Retina Off | Game started in 35.38s and exited normally; Steam left the same 64-bit overlay alive | `lifecycle-checks/20261016T231626489846Z/report.json` |
| Launch while orphan overlay remained | Immediate active-Wine-session refusal; did not reproduce the earlier Steam main-loop stall | `lifecycle-checks/20261016T231948890088Z/report.json` |
| Packaged 0.4.4 LG, two cold cycles | Both starts and all normal shutdown checks passed; no overlay recovery needed | `lifecycle-checks/20261016T232848814732Z/report.json` |
| Packaged built-in after LG | Started in 29.02s, game exited and policy restored; Steam shutdown inspection reported an unidentifiable browser helper, then all Wine processes exited | `lifecycle-checks/20261016T233204386856Z/report.json` |
| Built-in after bounded inspection fix, two cold cycles | Starts at 29.90s and 28.92s; both normal game/client/server exits and exact policy restoration passed | `lifecycle-checks/20261016T233606658329Z/report.json` |
| Actual 0.4.4 Play button, LG Retina Off | Startup timeout; specific failure visible in manager, policy restored, Steam Exit and manager Quit passed | `qualification/20261016-retina-hang/lg-stall-final-state.json` |
| Silent Steam launch candidate, LG Retina Off | Same startup timeout and Core Audio stack; no default change | `qualification/20261016-retina-hang/silent-candidate-final-state.json` |
| Steam-only audio-disable diagnostic, LG | Launch 30.06s and normal exits; diagnostic subsequently removed | `lifecycle-checks/20261016T235139755323Z/report.json` |
| Original audio restored, LG | Startup timeout recurred; prior policy restored; client later exited | `lifecycle-checks/20261016T235358393200Z/report.json` |
| Native original WinMM | Enumeration failed the 45-second watchdog; no game/client involved | `audio-checks/20261017T000005664776Z/report.json` |
| Native patched WinMM | Both architectures passed enumeration and all 23 silent output formats | `audio-checks/20261017T000107261594Z/report.json` |
| Patched WinMM, LG Retina Off, two cold cycles | Starts 29.75s/28.82s; game/client/server exits and exact policy restoration passed; no overlay recovery | `lifecycle-checks/20261017T000223252928Z/report.json` |
| Patched WinMM, built-in Retina On, three cold cycles | Starts 28.97s/28.80s/28.75s; all exits and restoration passed; no overlay recovery | `lifecycle-checks/20261017T000740885206Z/report.json` |
| Packaged 0.4.5 actual manager, built-in Retina On | Play, Exit Deadlock, Exit Windows Steam and Quit passed; `auto` restored | `qualification/20261016-retina-hang/manager-0.4.5-buttons.json` |
| Packaged 0.4.5, LG restored, cold cycle | Start 29.92s; all normal exits and exact restoration passed; no overlay recovery | `lifecycle-checks/20261017T001930021980Z/report.json` |

All evidence paths above are relative to private `DeadlockData`. The button-state
receipt was captured while startup was still waiting; subsequent process and
manager UI observations established exit outcomes. Steam and Deadlock are not
addressable by the current computer-use tool (`Invalid app: wine` / `steam.exe`).
Therefore no current visual, pointer, focus or gameplay pass is recorded.

The orphan was **gameoverlayui64.exe**, which our helper list omitted. Steam and
Deadlock were already gone. A normal Wine `taskkill` without `/F` could not find
a window to close. Test recovery sent SIGTERM only to the previously identified,
still-matching orphan PID after verifying its bottle and absent client/game;
Wine then exited. This recovery is not a normal-exit pass. The helper list now
includes both overlay architectures. The same orphan occurred on the LG, so this
shutdown defect is independent of the built-in Retina startup hypothesis.

The manager now offers this narrowly scoped recovery during Exit Windows Steam:
wait until only overlay helpers remain for five seconds, recheck that Deadlock
and Steam's client/browser/service are absent, and revalidate each overlay's
bottle ownership and start identity immediately before SIGTERM. Do not terminate
Steam, the game, another bottle or the whole Wine server. No SIGKILL escalation.
Verify complete Wine shutdown afterward. A helper that already exited or changed
identity is skipped and is not reported as a recovered process. The lifecycle
report records `overlay_recovery` separately from closure success.

A later run found a second lifecycle race: `lsof` could no longer resolve
`steamwebhelper.exe`'s cwd while `ps` still saw the process during shutdown.
All processes subsequently disappeared without intervention. The inspection now
rechecks at most three times, 100ms apart, retains start-identity checks, and still
fails if a live process remains unidentifiable. Successful output with no cwd is
also rejected. This handles a transient inspection result; it is not evidence
that the earlier Steam startup stall or orphan-overlay defect shares that cause.

The two LG and two built-in follow-up cycles all closed their overlays normally.
The new automatic orphan recovery path therefore has unit-test coverage plus the
earlier manually scoped SIGTERM recovery evidence; it has not yet been exercised
by a naturally recurring orphan in the rebuilt app. Do not invent that live pass.

## Upstream hypotheses checked

- Highball's Steam recipe distinguishes silent game launch from opening the
  client UI and describes synchronization-related CEF hangs. Our sanitized
  environment leaves `WINEMSYNC` and `WINEESYNC` unset in `auto`; the matched Wine
  source's `do_msync()` requires a nonzero variable. The upstream msync recipe
  is not evidence that our current configuration uses msync or needs that fix.
  [Recipe at inspected revision](https://github.com/gauthierpiarrette/highball-db/blob/483aac4628cc7d3209299fe283c506de05c6eb4e/recipes/launchers/steam.json)
- Highball's first-start recovery applies only before any successful login,
  after a completed bootstrap without a subsequent connection. This account is
  already signed in, so that recovery predicate does not apply. Do not copy its
  first-login restart into normal Play.
  [First-start predicate](https://github.com/gauthierpiarrette/highball/blob/b2c1e0dd172bbd629eaf05586906d2dc7dabb4c4/Sources/HighballKit/SteamFirstStart.swift)
- Valve's tracker has a Linux client report with the same main-loop assertion.
  It supplies a Steam-level lead, not a confirmed Wine/macOS diagnosis. A comment
  suggesting beta is not sufficient to change this user's client channel.
  [Valve issue 13576](https://github.com/ValveSoftware/steam-for-linux/issues/13576)
- The unrelated Retina GDI double-scaling patch did not reproduce in our API
  probe. See [the source review](GITHUB-RESEARCH.md); no such patch was applied.

## Fixes and next experiments

The manager now reads the detached Play outcome instead of leaving only a dispatch
acknowledgment visible. It distinguishes waiting, a running process, later
failure, interrupted ownership and restoration failure; receipts from another
workspace/profile cannot masquerade as this session. Startup timeout diagnosis
checks only a bounded tail of the current launch log. A recoverable Steam warning
does not abort a live game, and normal play still has no duration limit.

The silent `-applaunch` candidate failed and is not the proposed fix. The WinMM
candidate has a matching native reproducer, prerequisite review, conversion tests
and normal-audio live runs. Retain source hashes and separate build receipts;
stage a verified overlay without replacing the engine. Both target displays passed
startup/lifecycle runs, and packaged fresh/upgrade/rollback qualification passed
before the current local activation. Keep the
exit-only revision for rollback, and preserve explicit opt-out/rollback choices
during setup. Visual coverage, focus and audible game audio remain separate gates.

For a new startup failure, preserve Steam/client and browser samples, launch log,
selected target, loaded stack and process timeline before recovery. Do not assume
every main-loop timeout has the same cause or add silent retries that hide it.
Test Steam overlay lifecycle independently; do not disable the overlay globally
or label targeted recovery as a normal overlay exit.

Restore the saved LG target with Automatic Retina Off / 2560×1440 after built-in
experiments. Do not change the macOS main display or guess a disconnected target.
