# AGENTS.md

Hard-won context for agents working in this repository.

## Commands

```bash
python3 -m unittest discover -s tests      # full test suite (Kodi stubbed)
python3 -m unittest tests.test_logic.ResumeTests  # single test class
python3 -m compileall plugin.video.cumnation      # "build" (byte-compile)
python3 tools/build_repo.py            # regenerate repo/ after any add-on change
python3 tools/build_static_demo.py     # regenerate static demo content (only if demo_content.py changed)
```

No `requests` module in the test environment. Modules that need it (`trakt.py`)
must use a **lazy import** inside functions, not top-level.

## Architecture

- **Entry point:** `addon.py` → `router.py:Router.dispatch()` reads `?action=<name>` from URL
- **External I/O:** `content.py:ContentSource` only. Router never touches URLs directly.
- **Kodi API:** `kodiutils.py` only. No other module imports `xbmc*`.
- **Persistence:** JSON files in profile via `storage.py` (atomic writes: tmp→rename).
  Stores: `favorites.json`, `search_history.json`, `watch_history.json`, `resume.json`,
  `http_cache.json`, `sources.json`.
- **Resume tracking:** `ResumePlayer` (xbmc.Player subclass) polls `getTime()` ~1×/sec.
  Takes optional `video` parameter for Trakt scrobbling hooks.

## Critical conventions

1. **`repo/` is generated — never hand-edit.** Run `tools/build_repo.py` after every
   add-on change or version bump. `repo/**/*.zip` files MUST be committed (Kodi
   fetches them over raw GitHub URLs).

2. **Version bump sequence:** Edit `addon.xml` version → update `changelog.txt` →
   update `<news>` block in `addon.xml` → update `memory.md` version/test count →
   run `build_repo.py` → commit.

3. **Video metadata is version-safe:** Always use `kodiutils.set_video_info()`,
   never `ListItem.setInfo` or InfoTag setters directly. Dispatches on `kodi_major()`.

4. **User-facing strings:** Add `msgctxt "#32xxx"` entries to `strings.po`.
   Reference by numeric id via `kodiutils.get_string()` (aliased `S` in router).
   When adding a setting, also seed its default in `tests/kodistubs.py` `_Addon`.

5. **Content source contract:** Backends implement 4 endpoints relative to Base API URL:
   `/categories`, `/list`, `/search`, `/resolve`. Optional video fields: `preview`,
   `trakt_id`, `trakt_type`. Optional stream field: `subtitle` (URL).

## Kodi stubs (`tests/kodistubs.py`)

- `xbmcplugin`: empty module (no methods). Cannot call `xbmcplugin.addDirectoryItem`
  in tests without stubbing it.
- `xbmcvfs.translatePath`: identity function (paths are real filesystem paths).
- `xbmcvfs.rename`: `os.rename` (needed for atomic write tests).
- `xbmc.getInfoLabel`: returns `'20.2 (20.2.0) Git:20230000'` (major version 20).
- `_Addon.getSetting*`: returns seeded defaults from `settings.xml`.

## Test gotchas

- Importing `resources.lib.router` requires `requests` (via `content.py`). In tests,
  use lazy import or mock `sys.modules['requests']`.
- `Video.to_dict()` only includes truthy optional fields (preview, trakt_id, trakt_type).
- Stream objects have no `to_dict()` unless explicitly added — check current code.

## Branch workflow

Push to `main` directly (per project convention). CI runs on Python 3.9/3.11/3.12.
