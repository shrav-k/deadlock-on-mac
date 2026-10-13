# Local macOS app preview

The SwiftUI app runs the same Python manager as the CLI. Its pinned Apple Silicon
Python distribution and certificate store are bundled, while Wine, DXMT and Steam
are downloaded separately. The app never bundles game files or Steam account data.

Build on Apple Silicon with Python 3.12+ and Xcode command-line tools:

```sh
python3 packaging/build_app.py \
  --output '../Builds/local/Deadlock Manager.app' --downloads ../Downloads
```

Choose a new output path; the builder refuses to overwrite an existing application.
`python-lock.json` pins the Python archive URL and SHA-256. The build records source
hashes, compiler version and certificate hash in `Contents/Resources/build-inputs.json`,
and writes an adjacent file-hash manifest. This is recorded provenance, not a claim
of bit-for-bit reproducible Swift binaries.

Open the resulting app. Select the workspace, then **Set up Steam → Open Steam →
Install Deadlock → Play**. Steam owns sign-in, Steam Guard, game installation and
updates. First Steam startup can take several minutes. Performance changes require
Windows Steam to be closed; configure resolution after the game has run once.

The **Game Mode** panel selects a compatible Apple-signed `gamepolicyctl`. With
**Enable during Play** checked (the default), Play keeps Game Mode on for the
actual game process's lifetime, then restores the prior policy. There is no
play-time limit and the detached watcher survives closing this app. Status,
explicit end/restore and interrupted-Play recovery controls are included. The
Apple tool is not bundled; uncheck the option to play without it. The separate
collapsed diagnostic section retains the timed test and its recovery controls.
See the complete [installation and Game Mode guide](../docs/INSTALL.md).

The bundled Python interpreter runs with `-I -B`, an explicit manager import path,
an allowlisted environment and its included CA store. The app does not depend on
the player's Homebrew, Git, pip, compiler or separately installed Python.

This preview is ad-hoc signed for local development. It is **not notarized or a
public player release**. Do not disable Gatekeeper to distribute it. Public release
still requires Developer ID signing/notarization, a complete transitive dependency
and license inventory, upgrade/recovery testing and the gameplay acceptance gates
in [architecture](../docs/ARCHITECTURE.md). Bundled Python/Pip license files are
retained; that alone does not complete the distribution license audit.

## Include the reviewed exit overlay

After following [the source build guide](../docs/WINE-HOTFIX.md), add
`--wine-hotfix ../Runtimes/highball-exitfix-v1` to the app build command. The builder
verifies the DLL hashes and includes license/provenance. Fresh bootstrap stages
that payload and enables it before Steam starts, while honoring explicit rollback.
A source-only preview without this option does not include the hotfix. Public
distribution still requires corresponding-source/license review and notarization.
