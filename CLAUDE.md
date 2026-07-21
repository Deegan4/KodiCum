# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Kodi video add-on (`plugin.video.cumnation`) plus the machinery to distribute
it as a self-hosted Kodi repository straight from this GitHub repo. Targets
Kodi 19+ (Python 3). The add-on ships the browsing framework only — it reads
from a JSON content source the user configures; it bundles no content or
scrapers.

## Commands

```bash
# Run the full off-device test suite (Kodi is stubbed — no Kodi install needed)
python3 -m unittest discover -s tests

# Run a single test case or method
python3 -m unittest tests.test_logic.ResumeTests
python3 -m unittest tests.test_logic.ResumeTests.test_clears_when_finished

# Byte-compile the add-on (the closest thing to a "build")
python3 -m compileall plugin.video.cumnation

# Regenerate the installable repository after ANY add-on change or version bump
python3 tools/build_repo.py

# Exercise the whole add-on path (incl. playback) against a real backend:
#   serves CC-licensed Blender movies; point Base API URL at http://<ip>:8080
python3 plugin.video.cumnation/resources/lib/mock_server.py 8080
```

CI (`.github/workflows/ci.yml`) runs compile + XML validation + tests +
`build_repo.py` on Python 3.9/3.11/3.12.

## Architecture

**Add-on request flow.** Kodi invokes `addon.py` with the plugin URL in
`sys.argv` on every navigation and playback action; it is a thin launcher that
hands off to `resources/lib/router.py`. `Router.dispatch()` reads
`?action=<name>` from the URL and calls the matching `action_<name>` method.
Each action either builds a directory listing (folders/items via
`xbmcplugin.addDirectoryItem`, ending with `endOfDirectory`) or resolves and
plays a stream. Navigation state lives entirely in the URL query string —
there is no long-lived process.

**Content is abstracted behind a JSON API.** `resources/lib/content.py`
(`ContentSource`) is the only thing that talks to the outside world. It expects
four endpoints relative to the user-configured Base API URL:
`/categories`, `/list`, `/search`, `/resolve`. The router never knows where
data comes from — it only handles `Category`/`Video`/`Page`/`Stream` objects
from `models.py`. To support a new backend you implement that contract, not
add-on code. `mock_server.py` is a reference implementation of it (and is NOT
loaded by Kodi). `_get(..., cacheable=True)` layers the TTL cache (`cache.py`)
over categories/listings, and `_request()` retries transient failures with
exponential backoff; both are settings-driven.

**`/resolve` returns a list of `Stream`s; playback picks one.** A stream may be
progressive or adaptive (`manifest_type` hls/mpd/ism). `router._pick_stream`
applies the quality setting (Ask/Best/target resolution via
`models.select_stream`), and `router._apply_stream` wires progressive headers
onto the URL or, for adaptive streams, sets the `inputstream.adapter.*`
properties (manifest type, stream headers, optional Widevine/PlayReady DRM).
The single-stream `{"stream": ...}` shape is still accepted for older backends.

**Persistence is JSON files in the add-on profile.** `favorites.py`,
`history.py` (search + watch) and `resume.py` all go through
`storage.py`, which reads/writes JSON via `xbmcvfs` in
`ADDON_PROFILE`. These modules hold no Kodi-UI logic — the router calls them.

**Resume points are tracked manually.** Kodi does not persist resume positions
for plugin items. On playback, `action_play` sets `setResolvedUrl` then spins
up `player.ResumePlayer` (an `xbmc.Player` subclass) which polls
`getTime()` ~1×/sec and writes the final position to `resume.py` on stop/end.
Listings read that back to show a resume badge and set `StartOffset`.

**All Kodi API calls are funneled through `kodiutils.py`.** Nothing else
imports `xbmc*` for settings, dialogs, logging, or notifications. This is what
makes the logic testable off-device: `tests/kodistubs.py` registers fake
`xbmc`/`xbmcgui`/`xbmcaddon`/`xbmcvfs`/`xbmcplugin` modules in `sys.modules`
before the add-on is imported.

## Critical conventions

- **Video metadata is version-safe via `kodiutils.set_video_info()`.** Never
  call `ListItem.setInfo` or the `getVideoInfoTag().setX()` setters directly:
  `setInfo` is deprecated on Kodi 20+ (and will be removed), while the setters
  don't exist on Kodi 19. The helper dispatches on `kodiutils.kodi_major()` —
  InfoTag setters on 20+ (Nexus/Omega), `setInfo` fallback on 19 (Matrix).
  `addon.xml` declares `xbmc.python 3.0.0`, which covers Kodi 19–21.
- **The `repo/` tree is generated — never hand-edit it.** It is produced by
  `tools/build_repo.py` from the two add-on folders. `.gitignore` ignores
  `*.zip` but force-includes `repo/**/*.zip`; those zips MUST be committed
  because Kodi fetches them over raw GitHub URLs.
- **Bumping a version means editing `addon.xml` then rerunning
  `build_repo.py`** so `addons.xml` and `addons.xml.md5` regenerate. The
  repository add-on (`repository.cumnation/addon.xml`) hardcodes
  `raw.githubusercontent.com/Deegan4/KodiCum/main/...`, so the datadir must
  stay on `main`.
- **User-facing strings** live in
  `resources/language/resource.language.en_gb/strings.po` and are referenced by
  numeric id via `kodiutils.get_string()` (aliased `S` in the router). Add a
  `msgctxt "#3xxxx"` entry rather than hardcoding text.

## Layout

- `plugin.video.cumnation/` — the add-on (entry `addon.py`, logic in
  `resources/lib/`, UI in `resources/settings.xml` + language files). Skins can
  bind widget listings via `?action=widget&type=favorites|history|category`.
- `repository.cumnation/` — the Kodi repository add-on (pointers only)
- `repo/` — generated distributable repository (zips + `addons.xml` + md5)
- `tools/build_repo.py` — packages the two add-ons into `repo/`
- `tests/` — `unittest` suite + Kodi stubs
