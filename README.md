# Deadlock on Mac

Run Valve's **Deadlock** on Apple Silicon Macs at 60+ FPS. No Windows machine, no dual boot, no Parallels.

Full story of how this was figured out: [0ximu.dev/blog/deadlock-on-mac](https://0ximu.dev/blog/deadlock-on-mac)

## What you need

- Apple Silicon Mac (M1 or newer; the more GPU cores the better)
- macOS 14 Sonoma or newer
- ~80 GB free disk space (an external APFS SSD works great)
- A Steam account with Deadlock access

## Install (no terminal skills needed)

1. Download [`Install Deadlock.command`](https://github.com/0ximu/deadlock-on-mac/releases/latest) from the latest release.
2. In Finder, **right-click the file and choose "Open"** (a plain double-click gets blocked by macOS because the file is not notarized). Confirm the dialog.
3. A Terminal window opens and does everything: downloads the CrossOver trial engine from CodeWeavers, builds a self-contained `Deadlock.app` in your `~/Applications`, installs Windows Steam inside it, and launches Steam.
4. If you use a firewall app (LuLu, Little Snitch): **allow `wine` and `wine-preloader`** when asked, or Steam cannot go online.
5. Log into Steam (the QR code + Steam mobile app is the most reliable way), install Deadlock from your library, press Play.

Want it on an external drive? Run instead:

```sh
curl -fsSL https://0ximu.dev/deadlock-mac-setup.sh | zsh -s -- /Volumes/YourDrive/Deadlock.app
```

## After install

- Launch by opening `Deadlock.app`. It cleans up stale wine processes on every start and keeps launch logs in `Deadlock.app/Contents/SharedSupport/Logs`.
- The first session stutters while shaders compile. That is normal and goes away.
- Start at 1440p / Medium settings. M-Max chips handle High at 60+.
- Debug overlay (Apple's Metal HUD): `DEADLOCK_HUD=1 open ~/Applications/Deadlock.app`

## How it works

Three translation layers, all local:

| Layer | Job |
|-------|-----|
| wine 10/11 (CrossOver 26+ build) | Windows syscalls → macOS. Older wine (9.x, standalone GPTK) can no longer run the 2026 Steam client. |
| D3DMetal (Apple Game Porting Toolkit, ships inside CrossOver) | DirectX 11 → Metal |
| Rosetta 2 | x86-64 → ARM |

The launcher exports `CX_ROOT`, `CX_GRAPHICS_BACKEND=d3dmetal` and the `libd3dshared` path. Without those, CrossOver's `cxcompatdb.so` silently skips the D3DMetal redirect and you get wine's fallback renderer at ~10 FPS. That trap alone justified this repo.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `Download failed: http error 0`, Steam "needs to be online" | Firewall silently blocked wine. Allow `wine` + `wine-preloader`. |
| `steamwebhelper is not responding` or `Transport Error (0x3008)` | Wine build too old for current Steam. Re-run the installer to get a current CrossOver engine. |
| Game renders fine but ~10 FPS, GPU half idle | wined3d fallback. Verify with `lsof -p $(pgrep -f deadlock.exe) \| grep -oiE 'D3DMetal\|wined3d'` - if no D3DMetal, the launcher env is not reaching the game; launch via `Deadlock.app`, not a bare `wine` call. |
| Works from Terminal, "unable to write to its folder" from Finder | App Translocation. The generated launcher uses absolute paths to avoid it; do not move the app without re-running `xattr -cr` + `codesign -f -s -` on it. |
| Random stutter, everything looks idle in `ps` | Orphaned wine processes or background builds. `sudo powermetrics -n 1 -i 3000 --samplers tasks \| head -30` shows the truth; the launcher sweeps orphans on start. |
| Steam login freezes at the 2FA step | Use the QR code with the Steam mobile app instead. |

## Fine print

- The installer downloads the **CrossOver trial** from CodeWeavers' own servers and builds everything locally; nothing proprietary is redistributed here. If this setup sticks, [buy a CrossOver license](https://www.codeweavers.com/store) - CodeWeavers fund a huge share of wine development.
- Deadlock uses user-mode VAC today and wine players are not being banned, but Valve does not support this setup. A future anti-cheat change could break it. You accept that risk.
- Not affiliated with Valve, CodeWeavers, or Apple.

## License

MIT for the scripts in this repo.
