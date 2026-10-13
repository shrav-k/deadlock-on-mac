# Deadlock on Mac — Steam-first, free-runtime workbench

Run Valve's **Windows Steam client with your existing Steam account**, then install
and launch Deadlock from that library. This maintained fork aims to make a durable
unpaid setup easy to test, diagnose and update.

**Status: experimental. Deadlock gameplay is not yet verified by this fork.**
See the [compatibility ledger](docs/COMPATIBILITY.md) for observed results rather
than inferred compatibility.

The default free candidate is **Highball's Wine 11 build + its paired DXMT build**.
Steam login, installation and a Direct3D rendering probe work on our M2 Max.
**The first Deadlock launch crashed; gameplay is not ready.** A Sikarugir Wine 11 + upstream DXMT 0.80 pair remains available for
comparison, with a known black Steam login window on this Mac. Official
CrossOver is an optional comparison provider; the project does not depend on a
CrossOver trial. Every profile owns a separate Steam environment so runtime
experiments preserve the existing setup.

## Start here

Place the repository inside `Projects/Games/Deadlock`. Requires Apple Silicon, macOS 15+,
Rosetta 2 and Python 3.12+. Review [security boundaries](SECURITY.md), then:

```sh
python3 bin/deadlock-mac runtime-install
python3 bin/deadlock-mac profile-create
python3 bin/deadlock-mac setup
python3 bin/deadlock-mac steam
```

Sign into **your existing account in Steam**. Then install and play:

```sh
python3 bin/deadlock-mac install
python3 bin/deadlock-mac launch
python3 bin/deadlock-mac doctor
```

Steam manages game downloads, updates, entitlement, friends and any supported
Cloud files. The manager never launches `deadlock.exe` directly or reads your
credentials. Deadlock's public listing does not currently advertise Steam Cloud;
verify the in-client options and keep local backups instead of assuming all
settings sync. [Installation and account guide](docs/INSTALL.md)

## Layout

```text
Projects/Games/Deadlock/
  deadlock-on-mac/    source, tests and documentation only
  Downloads/          verified runtime and Steam installers
  Runtimes/           side-by-side runtime versions
  Bottles/            one Windows Steam environment per profile
  DeadlockData/       private profiles and logs
  DeadlockBackups/    local Deadlock data snapshots
  Tools/              optional diagnostic compiler
  deadlock-audit-*/   local audit evidence (not published)
```

No administrator privileges, native Steam modifications, trial resets, automatic
Cloud-conflict choices, or global process kills. Wine is not a security sandbox.
The manager has no third-party Python dependencies.

## Develop and compare

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 bin/deadlock-mac profiles
python3 bin/deadlock-mac runtimes
python3 bin/deadlock-mac launch --dry-run
python3 bin/deadlock-mac runtime-verify
python3 bin/deadlock-mac runtime-dependencies
```

- [Runtime research, alternatives and upgrades](docs/RUNTIMES.md)
- [Module boundaries, packaging plan and release gates](docs/ARCHITECTURE.md)
- [Tests, gameplay acceptance and performance comparisons](docs/TESTING.md)
- [Observed compatibility](docs/COMPATIBILITY.md)
- [Security and provenance limitations](SECURITY.md)
- [Changes from upstream](CHANGELOG.md)

Source code is MIT licensed. Runtime components have their own licenses and are
downloaded separately. This project is not affiliated with Valve, Apple,
CodeWeavers, WineHQ or Sikarugir. Original upstream attribution is retained in
[LICENSE](LICENSE) and Git history.
