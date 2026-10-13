# Upstream Wine backports

These patch files retain their upstream authorship and original bytes. They are
Wine source changes under LGPL-2.1-or-later, not the manager's MIT license. See
Wine's COPYING.LIB in the pinned source archive and the license retained with the
built overlay. Only the sechost/service.c portions are applied by this repository's
matched-source build; native regression probes live in tests/native/.

Commit URLs, archive and per-patch hashes, source recipe and build constraints are
recorded in config/wine-hotfix.json and docs/WINE-HOTFIX.md. Do not edit a patch or
replace its digest without reviewing and retesting the resulting runtime.
