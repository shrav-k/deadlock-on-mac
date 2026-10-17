# Window capture and observed input

Diagnostics → Visual testing captures Windows Steam, Deadlock or the test grid
through ScreenCaptureKit. The native worker is part of Deadlock Manager; it writes
one window's composited image, including Metal content, rather than recording the
desktop or audio. A window in another Space can be captured. Minimized/hidden
windows may have stale or unavailable content; inspect every image before acting.

The user grants **Screen & System Audio Recording** for capture and **Accessibility**
for input in macOS Privacy & Security. The worker reports actual permission state.
Use the request actions to open Apple's prompts, then retry. Ad-hoc development
rebuilds can require renewed approval; public distribution needs a stable Developer
ID signature and notarization. Never alter the TCC database or bypass prompts.

```sh
bin/deadlock-mac visual status
bin/deadlock-mac visual request-screen
bin/deadlock-mac visual request-input
bin/deadlock-mac visual windows --target steam
bin/deadlock-mac visual capture --target steam
```

The capture response includes an absolute PNG path, image dimensions, window and
process identity, and a capture ID. Open that PNG before selecting a control. If
several windows exist, `--window ID` selects one from `visual windows`.

```sh
bin/deadlock-mac visual enable-input
# Coordinates are pixels in the full PNG, not a resized preview or desktop points.
bin/deadlock-mac visual click --capture CAPTURE_ID --x 400 --y 200
bin/deadlock-mac visual key --capture NEW_CAPTURE_ID --key escape
bin/deadlock-mac visual stop-input
```

An input session expires after four hours and can be revoked immediately. Each
action consumes a capture less than 60 seconds old, verifies its image hash,
profile, process start identity and current window bounds, then verifies foreground
application/window before delivery. Keyboard events go to that PID. Mouse input
also verifies the topmost window at the click point, positions the pointer, and
uses WindowServer routing: direct per-PID mouse posting did not activate Wine
controls in live testing. Retina and negative external
display coordinates are mapped from the full PNG. A failure consumes the receipt
too: capture again rather than retrying an event with an unknown result.

Each action returns a new screenshot. `events_posted` means dispatch only; inspect
the new image to establish that the intended control changed. No success is inferred
from mouse/keyboard delivery alone. Supported input is one left click or a named
navigation/game key; arbitrary text, chords, macros and public-match automation
are not supported. Account login, Steam Guard, purchases, chat and matchmaking
remain user-operated.

For private sandbox navigation, `visual key --capture ID --key w --hold-ms 1000`
holds one movement key for at most one second. Only W/A/S/D accept holds; other
keys remain short taps. The worker checks focus and revocation every 40 ms and
releases on failure. Inspect the resulting image before another movement. Q is
available for the observed Mina ultimate binding; never use this in a public match.
E supports the lobby's observed interaction prompt.

Images, receipts and action records stay under `DeadlockData/visual/<profile>/`,
outside Git, with private file permissions. They can contain account/friend names;
do not publish raw captures. Capture refuses after 512 MiB of existing PNGs, rather
than deleting evidence automatically. Review and remove old captures as needed.
Capture/encoding can affect frame time: take comparison images outside measured
benchmark intervals and mark any focus changes.

## Why not capture inside Wine?

Windows [PrintWindow](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-printwindow)
asks an application to draw into a device context and is synchronous. That does
not establish that it reproduces a Metal-backed game swapchain. Host
[SCScreenshotManager](https://developer.apple.com/documentation/screencapturekit/scscreenshotmanager)
captures the composited window without game injection. Input uses Apple's public
[CGEvent posting API](https://developer.apple.com/documentation/coregraphics/cgevent/posttopid(_:))
with explicit permissions and process/window checks. No replacement game DLL or injected
overlay is required.

## Verification

Python tests exercise receipt expiry/reuse, revocation, process reuse, tampering,
unrelated windows, storage bounds and unknown outcomes. Native tests exercise
Retina/external coordinate mapping and invalid coordinates. Live acceptance must
also demonstrate screenshots with visible Metal content, a click and key producing
the intended change, permission denial, focus/window changes failing safely, and
clean target exit. Automated unit tests alone do not establish working input.

### Local acceptance, 2026-10-17

On the M2 Max, the worker captured Steam on the built-in display (1280×800 points,
2560×1600 PNG) and Deadlock on the secondary LG (2560×1440, negative desktop Y).
An observed Steam Library click and Deadlock menu clicks changed the intended views.
Return advanced the title screen; Escape opened the menu; bounded W movement and E
opened the lobby's play-mode selector. Selecting Sandbox loaded Mina, and Q visibly
triggered her ultimate. The manager exit command closed the game normally and
restored Game Mode to its previous automatic policy, with Steam left open.

Covered click points and a different Steam popup were rejected without sending
input. Permission revocation, stale captures, PID reuse and interrupted holds have
automated coverage; live permission revocation remains a separate acceptance check.
The general UI connection still failed on manager interactions, so the synthetic
manager snapshots do not establish a live check of every new Diagnostics button.

A 10-second process-attached Instruments Time Profiler recording also completed.
Its table-of-contents export succeeded, but Xcode 27.1's backtrace XML exporter
crashed while exporting the time-profile table; CPU hotspot analysis remains
unverified. Keep the trace and exporter crash report for follow-up.
These checks qualify the observation/control workflow, not a performance claim:
the pre-existing Low preset had `mat_viewportscale=0.5`, and no graphics settings
were changed during this acceptance run. Resolve that conflict with the required
native-rendering policy before using the run as a performance baseline. Raw images,
action receipts and the trace remain private in the workspace.
