# Changelog

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

Forked from `0ximu/deadlock-on-mac` at
`aedcd5128613b6f94e228d6258840b33fdb53782`. Original history and MIT attribution
are retained. Original installer paths are removed from this branch.
