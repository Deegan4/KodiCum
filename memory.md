# Project Memory — KodiCum / Cumnation

Running context for the project. Update this as decisions and state change.

_Last updated: 2026-09-23_ (v1.1.7 batch)

## What this is

`plugin.video.cumnation` — a Kodi video add-on, plus the machinery to
distribute it as a self-hosted Kodi repository straight from this GitHub repo.
The add-on ships the browsing framework only; it reads from a JSON content
source the user configures, and bundles no content or scrapers.

- **Target:** Kodi 19+ (Matrix through Omega). ABI `xbmc.python 3.0.0`.
- **Runtime dependency:** `script.module.requests` only.
- **Distribution repo path (hardcoded in `repository.cumnation`, v1.0.1+):**
  `https://deegan4.github.io/KodiCum/` (GitHub Pages, published from
  `repo/zips/`). The `repo/` tree itself must still be pushed via `main`
  (that's what Pages is configured to publish); only the URL baked into
  installed clients changed from a raw-GitHub `main`-branch path to one
  that isn't tied to the branch name.
- **File manager source URL:** `https://deegan4.github.io/KodiCum/` (GitHub
  Pages, published from `repo/zips/` by `.github/workflows/pages.yml`). The raw
  URL can't be used as a source — raw GitHub can't list directories.

## Current state

- **Add-on version:** `1.1.7` (`plugin.video.cumnation/addon.xml`).
- **Repository add-on version:** `1.0.1` (`repository.cumnation/addon.xml`).
- **Branch/PR:** work happens on `claude/session-0pl4np` and is pushed to both
  that branch and `main`. PR #1 was merged. Development continues by pushing
  to `main` directly (per user instruction "push to main").
- **Tests:** 158 `unittest` tests, all passing (`python3 -m unittest discover -s tests`).
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
- **Preview images (1.1.4):** videos may include an optional `preview`
  field (URL to a still/animated frame). When present it is displayed
  as the listing's fanart/background image; `thumb` remains the poster.
- **Skin widgets + diagnostics (1.0.2):**
  `?action=widget&type=favorites|history|category`; a "Test connection"
  settings button; a "Clear content cache" action.
- **Preview images (1.1.4):** videos may include an optional `preview`
  field (URL to a still/animated frame). When present it is displayed
  as the listing's fanart/background image; `thumb` remains the poster.
- **Resume badges (1.1.5):** partially-watched videos show a progress
  label (percentage) via `Progress` and `ResumeLabel` ListItem properties.
- **Trakt scrobbling (1.1.5):** track watch progress on Trakt.tv
  (`trakt_enabled`, `trakt_username`, `trakt_api_token` settings;
  `trakt_id`/`trakt_type` on videos).
- **Subtitle support (1.1.5):** streams may include a `subtitle` URL
  passed to Kodi via `ListItem.setSubtitles()`.
- **Content source switcher (1.1.5):** multiple sources managed via
  `sources.json`, switchable from the root menu.
- **Cache size limit (1.1.5):** `MAX_ENTRIES = 500` with oldest-eviction.
- **v1.1.6 fixes:** the `base_url` setting was completely disconnected from
  `ContentSource` (it only read `sources.active_url()`, always `''` by
  default) — every request 32050'd regardless of what was typed in
  Settings. `action_switch_source` also crashed on every use
  (`UnboundLocalError`, shadowed the `sources` module import with a local
  of the same name). Both fixed; see `ContentSourceBaseUrlTests` and
  `test_switch_source_lists_sources_without_crashing` in `test_logic.py`.
- **Static (no-server) sources (1.1.6):** a source can be marked `static`
  (per-source flag, or the `base_url_static` setting for the legacy
  single-URL field). `ContentSource` then requests fixed paths —
  `{base}/categories.json`, `{base}/list/{category}/{page}.json`,
  `{base}/resolve/{id}.json` — instead of query strings, so a plain file
  host with zero server-side logic works. `tools/build_static_demo.py`
  bakes `resources/lib/demo_content.py` (shared with `mock_server.py`)
  into that layout, published at
  `https://deegan4.github.io/KodiCum/demo-content/` — a free, no-computer
  way to try the add-on end to end.
- **v1.1.7:** Manage sources root-menu screen (add/rename/remove/switch,
  `sources.py` `add_source`/`rename_source`/`remove_source`/`set_static`);
  fixed `rename_source` never persisting and a dropped `{0}` in the
  switch-source notification. Multiple subtitle tracks
  (`Stream.subtitles`, a list, alongside the existing single
  `subtitle`). Static sources can search via an optional
  `search-index.json`. `tools/build_static_source.py` turns a folder of
  your own videos into a static source. `build_repo.py`'s zips are now
  byte-identical across reruns of identical sources. New
  `.github/workflows/pages-healthcheck.yml` (daily + post-publish).
  `repository.cumnation` bumped to 1.0.1 (its own update URLs moved to
  Pages).

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

Static sources (no server) use fixed paths instead:
`/categories.json`, `/list/{category}/{page}.json`, `/resolve/{id}.json`,
and an optional `/search-index.json` (flat `{"videos":[...]}`, fetched once
and filtered client-side by title). `tools/build_static_demo.py` and
`tools/build_static_source.py` both generate this layout.

## Open threads / not yet done

- **Parental PIN lock** — proposed, user did NOT select it. Available on request.
- Repository URLs are hardcoded to `Deegan4/KodiCum` on GitHub Pages
  (since v1.0.1, no longer tied to `main` specifically) — renaming the
  *repo itself* would still break installed clients' updates (the
  `deegan4.github.io/KodiCum/` URL is derived from the repo name);
  renaming the default *branch* no longer would.
