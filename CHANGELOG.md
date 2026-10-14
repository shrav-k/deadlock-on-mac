# Changelog

## 0.2.2 — development

- Keep operation feedback beside Exit controls, display elapsed time and periodic
  shutdown countdowns, and explain recovery when Steam does not process a request.
- Test explicit manager quit after a failed operation. The live Steam shutdown
  failure after a client update is still under investigation; no fix is claimed.

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
