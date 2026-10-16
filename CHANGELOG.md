# Changelog

## 0.4.4 — development

- Show detached Play startup, delayed failure, process readiness and Game Mode
  restoration on the Play page; isolate status by workspace/profile and bound
  read-only helper output. Closing the manager still leaves Play ownership intact.
- Identify a Steam main-loop stall at the startup deadline using only the current
  launch log. Do not abort on a recoverable warning or claim a Retina root-cause fix.
- Include Steam's 64-bit overlay in shutdown verification. If only orphaned
  overlays remain for five seconds after the game/client/browser/service exit,
  recheck bottle ownership and process identity before sending SIGTERM to those
  helpers only. Report recovered shutdown separately from normal overlay exit.
  Record requested synchronization environment in private launch evidence.
- Briefly recheck a helper that loses its working directory during shutdown;
  still reject a live process whose bottle cannot be identified. Cover exit,
  transient inspection failure, PID reuse and missing-cwd results with tests.
- Add synthetic manager snapshot fixtures and isolated status-reader tests;
  fix clipped display instructions at narrow widths. Document the remaining
  Retina/Steam uncertainty and separate UI/replay/sandbox qualification lanes.

## 0.4.3 — development

- Wait for the selected Wine server to finish after Windows Steam exits, so
  immediate relaunch/display checks do not reject its normal shutdown grace period
  as another active Wine session. Timeout is explicit; no force termination.
- Qualify fresh Game Mode preparation from official Xcode 27.1 on macOS 26.6.2
  using the packaged interpreter in an empty workspace. Add strict provenance,
  first-run, missing-tool, cache and policy-preservation regression checks.
- Document installation prerequisites and an ordered autonomous qualification
  plan for both displays, lifecycle, controlled sandbox and performance work.
- Consolidate pinned GitHub project research and add a read-only Windows display
  API probe. The local probe does not reproduce the upstream extra GDI doubling.

## 0.4.2 — development

- Package pinned FFmpeg libraries matching Highball's ABI and re-export bindings;
  verify and install them atomically without changing the original runtime.
- Add an owned-file decode probe and 32/64-bit Wine media bridge checks in a
  disposable prefix, plus setup/integrity regression tests. No gameplay required.
- Discover compatible Apple Game Mode tools automatically and prepare a verified
  local copy for launch/recovery. Check this prerequisite before Steam setup;
  provide an explicit opt-out and Xcode setup guidance when unavailable.
- Keep advanced tool selection optional and separate Game Mode preparation from
  display preparation. Apple tooling remains an explicit prerequisite on fresh Macs.

## 0.4.1 — development

- Define workspace ownership/cleanup and record deployment gaps; outline a shared
  launcher core with versioned game recipes without claiming general-game support.
- Publish local previews at one stable app path with opt-in verified replacement,
  one rollback app and bounded provenance history. Reject active manager/watchers
  and changed app trees; test build failure, publication rollback and recovery.
- Show prepared output size and resolved Retina state on Play, and distinguish
  desktop coordinates from current backing pixels in Settings.
- Explain Game Mode as a launch policy, including opt-out leaving the existing
  system policy unchanged. Keep lifetime/restoration behavior independent of
  the chosen display and the manager window.
- Refuse Play when display choices have not been applied; refresh the prepared
  summary after applying. Cover laptop/external Retina transitions, high-DPI
  external displays and launch-policy presentation with automated tests.
- Document the bottle-wide Retina limitation and the built-in display acceptance
  sequence. Fullscreen visual results remain separate from policy tests.

## 0.4.0 — development

- Replace the long control panel with Play, Settings and Diagnostics sidebar pages.
  Keep Stop/Restore and operation feedback visible across pages. Preserve the
  existing Steam-only launch and exit commands and manager quit lifecycle.
- Cancel diagnostics through a private manager-to-worker pipe rather than a
  process-group signal. Test actual AppKit close/quit/Stop with a child process
  that must acknowledge pipe closure; parent loss uses the same close request.
- Save grid output incrementally, including stderr and partial failure logs.
- Add an opt-in SDL fullscreen-desktop grid using the installed game's SDL3 and
  the same D3D11 renderer as the popup baseline. It retains the current desktop
  mode, reports settled geometry and does not prove exclusive-fullscreen support.
- Built-in visual qualification is in progress; external-display and gameplay
  tests remain pending. No fullscreen or performance fix is claimed yet.

## 0.3.1 — development

- Respond to Wine's cooperative activation request after manager-initiated Play,
  Steam or grid launches. Require the selected prefix and engine, an active manager,
  and a short startup interval; never move windows or change macOS Spaces.
- Keep the grid open until Escape/Close or Stop Grid. Stream its readiness/click
  events, record the close reason, and close the owned helper if its parent exits.
- Cover cancellation, busy manager close/quit, and activation eligibility with
  automated tests. The user never saw the previous LG game window; this remains
  an unresolved visual acceptance failure until the new handoff is checked live.

## 0.3.0 — development

- Add a named display picker, main-display/external preferences and separate Retina
  policy. Preparing a display backs up game settings and changes only its bottle;
  the macOS primary display and desktop modes are never changed.
- Map native display identity/geometry to the installed game's SDL enumeration,
  and reject missing/ambiguous targets or changed layouts/settings before Play.
- Add a bounded borderless D3D11 test grid with click/focus evidence, plus packaged,
  hash-verified native helpers built with a pinned Windows compiler.
- Add display selection, rollback, hotplug, configuration-change and UI-model tests.
  The LG test grid and Steam-launched game closed normally through the manager;
  live menu coverage, pointer and Command–Tab acceptance remain pending.

## 0.2.2 — development

- Keep operation feedback beside Exit controls, display elapsed time and periodic
  shutdown countdowns, and explain recovery when Steam does not process a request.
- Test explicit manager quit after a failed operation. The live Steam shutdown
  failure after a client update is still under investigation; no fix is claimed.
- Add opt-in Steam-only idle/restart/shutdown qualification, with tests ensuring
  it never launches a game, closes a user-started game or force-kills a client.
- Verify actual busy red-close and Command–Q behavior after scoped Steam recovery;
  retain the underlying client hang as unresolved rather than claiming a fix.
- Add native host and guest display inventory probes, compare the free runtime
  with an isolated official CrossOver bottle, and document the observed mixed-DPI
  coordinate mismatch. No secondary-display game acceptance is claimed.
- Review CodeWeavers installation, graphics, DPI, logging and bottle practices;
  propose a monitor picker that preserves the user's macOS primary display.

## 0.2.1 — development

- Own the manager window and application lifecycle in AppKit while retaining the
  SwiftUI interface. The actual 0.2.0 red-close check exposed premature manager
  termination with a shutdown worker still running.
- Cancel busy quit requests and resubmit after successful worker completion on
  the normal event loop; leave failures visible and finish diagnostic cleanup.
- Add eight native application integration scenarios with the real close button,
  app quit action and isolated fake workers, plus a macOS 15 CI job.
- Research external-display hotdesking, refresh/pacing, upstream DXMT resize fixes,
  current Wine/renderer candidates and Rosetta alternatives without changing the
  installed game runtime or claiming unmeasured performance gains.

## 0.2.0 — development

- Replace the unreliable Wine close-window request with Steam's non-forced
  app-specific stop and verify actual game exit plus Game Mode restoration.
- Add Exit Windows Steam with game-first shutdown, helper-process checks and
  idempotent no-op exits; preserve native Steam and unrelated profiles.
- Add explicit Quit Manager and a single-window lifecycle that waits for active
  operations and restores timed diagnostics before quitting.
- Persist workspace/profile selection, stream unbuffered output, bound UI log
  memory and remove the laptop-specific fullscreen resolution default.
- Stage app builds transactionally, smoke-test bundled CLI/version before signing,
  and test packaging failures and the Swift quit policy in automation.
- Add an opt-in menu-only lifecycle harness; gameplay/external-display acceptance
  remains paused and separately tracked.

## 0.1.0 — development

- Replace the original CrossOver extraction installer with a Steam-first manager.
- Make pinned standalone Wine + DXMT the experimental unpaid default.
- Keep an optional adapter for the intact official CrossOver app.
- Give every runtime profile a dedicated Steam prefix and keep state outside Git.
- Add verified downloads, archive validation, atomic state, local game-data backups,
  selected diagnostics and automated tests.
- Document runtime provenance, licensing limits, account/Cloud behavior, research
  alternatives and an explicit gameplay acceptance gate.
- Report immediate runtime-loader failures with the private log location.
- Add a preflight/bootstrap command and a local SwiftUI preview with pinned bundled Python.
- Add reversible FPS-cap, Wine synchronization and Metal HUD settings, power diagnostics,
  backed-up display edits and per-process performance-log summaries.
- Exercise the app's clean installation path through Steam sign-in and a fresh game download;
  record first-launch failure and a successful normal Steam retry separately.
- Add optional Apple-signed Game Mode tool diagnostics, bounded comparisons and
  interrupted-test recovery; record the user-observed Mina sandbox improvement.
- Make manager Play own a detached Game Mode session with no gameplay deadline,
  prior-policy restoration, bottle/PID matching, concurrency protection and recovery.

- Add normal Exit Deadlock, a reversible hash-verified Wine exit backport, matched-source
  build recipe, dual-architecture native probes and a newer Wine comparison harness.
- Add private gameplay markers/reports, frame-time tails, explicit runtime promotion
  gates, and backed-up borderless display recovery.
- Add an opt-in, reversible Wine Retina setting for high-resolution borderless
  experiments; extend the native display probe with mode enumeration, explicit
  resolution sequences and desktop restoration checks.
- Add backed-up game/menu FPS-limit editing and preserve configuration line endings;
  record the successful Retina-borderless coverage/input/app-switching test separately
  from unresolved fullscreen and delayed-exit behavior.

Forked from `0ximu/deadlock-on-mac` at
`aedcd5128613b6f94e228d6258840b33fdb53782`. Original history and MIT attribution
are retained. Original installer paths are removed from this branch.
