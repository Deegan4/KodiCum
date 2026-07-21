# Project Memory — KodiCum / Cumnation

Running context for the project. Update this as decisions and state change.

_Last updated: 2026-07-21_

## What this is

`plugin.video.cumnation` — a Kodi video add-on, plus the machinery to
distribute it as a self-hosted Kodi repository straight from this GitHub repo.
The add-on ships the browsing framework only; it reads from a JSON content
source the user configures, and bundles no content or scrapers.

- **Target:** Kodi 19+ (Matrix through Omega). ABI `xbmc.python 3.0.0`.
- **Runtime dependency:** `script.module.requests` only.
- **Distribution repo path (hardcoded in `repository.cumnation`):**
  `raw.githubusercontent.com/Deegan4/KodiCum/main/repo/zips/` — so the
  generated `repo/` tree must stay on `main`.

## Current state

- **Add-on version:** `1.0.2` (`plugin.video.cumnation/addon.xml`).
- **Repository add-on version:** `1.0.0` (`repository.cumnation/addon.xml`).
- **Branch/PR:** work happens on `claude/session-0pl4np` and is pushed to both
  that branch and `main`. PR #1 was merged. Development continues by pushing
  to `main` directly (per user instruction "push to main").
- **Tests:** 23 `unittest` tests, all passing (`python3 -m unittest discover -s tests`).
- **CI:** `.github/workflows/ci.yml` runs compile + XML validation + tests +
  repo rebuild on Python 3.9/3.11/3.12.

## Features implemented

- Categories (paginated), search + persistent search history, favorites,
  watch history, resume points.
- **Latest-Kodi compatibility (1.0.1):** `kodiutils.set_video_info()` uses the
  InfoTagVideo API on Kodi 20+ and falls back to `setInfo` on Kodi 19; dropped
  the unused beautifulsoup4 dependency.
- **Adaptive streaming (1.0.2):** `/resolve` returns a list of `Stream`s;
  HLS/DASH/ISM play via InputStream Adapter with optional Widevine/PlayReady
  DRM. Progressive streams keep header-on-URL. Single `{"stream":...}` shape
  still accepted.
- **Quality selection (1.0.2):** Ask / Best / preferred resolution
  (`models.select_stream`).
- **Caching + retry (1.0.2):** `cache.py` TTL cache over categories/listings;
  `ContentSource._request` retries transient failures with backoff.
- **Skin widgets + diagnostics (1.0.2):**
  `?action=widget&type=favorites|history|category`; a "Test connection"
  settings button; a "Clear content cache" action.

## Key decisions / conventions

- **Never call `ListItem.setInfo` or InfoTag setters directly** — always go
  through `kodiutils.set_video_info()` (version dispatch on `kodi_major()`).
- **`repo/` is generated — never hand-edit.** Produced by
  `tools/build_repo.py` from the two add-on folders. `.gitignore` ignores
  `*.zip` but force-includes `repo/**/*.zip` (Kodi fetches those over raw URLs).
- **Bumping a version = edit `addon.xml`, then rerun `tools/build_repo.py`** so
  `addons.xml` + `addons.xml.md5` regenerate. Also update `changelog.txt` and
  the `<news>` block.
- **All external I/O flows through `ContentSource`**; all Kodi API through
  `kodiutils`. This is what makes off-device tests possible via
  `tests/kodistubs.py` (fake xbmc modules in `sys.modules`).
- **User-facing strings** live in `strings.po`, referenced by numeric id via
  `kodiutils.get_string()` (`S` in the router). New settings need new ids.
- When adding a setting, also seed a default in `tests/kodistubs.py` `_Addon`
  so off-device tests match Kodi's default-return behaviour.

## Content source contract (what a backend must implement)

`GET /categories`, `/list?category=&page=&limit=`, `/search?q=&page=&limit=`,
`/resolve?id=[&url=]`. Full shapes documented in
`plugin.video.cumnation/README.md` and `resources/lib/content.py`.
`resources/lib/mock_server.py` is a runnable reference backend (CC Blender
movies; demonstrates the multi-quality `/resolve` shape).

## Open threads / not yet done

- **Parental PIN lock** — proposed, user did NOT select it. Available on request.
- Other ideas floated, not started: multiple switchable content sources,
  subtitle-track support from `/resolve`, Trakt scrobbling.
- Repository URLs are hardcoded to `Deegan4/KodiCum@main` — moving/renaming the
  repo or default branch would break installed clients' updates.
