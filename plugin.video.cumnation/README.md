# Cumnation — Kodi video add-on

A configurable video add-on for [Kodi](https://kodi.tv) (Matrix / Nexus /
Omega, i.e. Kodi 19+ with Python 3). It gives you a full browsing UI —
categories, search, favorites, watch history and resume — on top of a content
source you configure. The add-on is **content-source agnostic**: it reads from
a small JSON API whose URL you set in the add-on settings, so it is not tied to
any single website and ships nothing but the framework.

## Features

| Feature | Details |
| --- | --- |
| **Categories** | Browse the source's category tree, with per-page loading and a *Next page* item. |
| **Search** | Keyboard search with a persistent, de-duplicated search-history list. Remove single terms or clear all. |
| **Favorites** | Add/remove from the context menu; a dedicated Favorites folder; clear-all. |
| **Watch history** | Recently watched items are remembered (toggleable, size-capped). |
| **Resume** | Partially watched items resume where you left off; finished items reset automatically. |
| **Subtitles** | A stream may carry one subtitle URL or several (one per language); all are handed to Kodi's own subtitle picker. |
| **Multiple sources** | Add, rename, remove and switch between named content sources (each optionally static) from **Manage sources** on the root menu — no need to retype the URL to try another. |
| **Adaptive streaming** | Plays HLS/DASH/SmoothStreaming via InputStream Adapter, with optional Widevine/PlayReady DRM. |
| **Quality selection** | When the source returns several renditions: *Ask*, *Best available*, or a preferred resolution. |
| **Caching & retries** | TTL cache for categories/listings and automatic retry-with-backoff on transient errors. |
| **Skin widgets** | Favorites / history / a category can be bound as home-screen widgets. |
| **Device discovery** | Finds DLNA/UPnP renderers — smart TVs, AV receivers, streaming sticks — on your local network. |
| **Casting** | Play any item on a discovered TV via UPnP AVTransport, with pause/resume/stop controls. |
| **Settings** | Base API URL, user-agent, page size, quality, cache/retry, resume/history toggles, device discovery, connection test and maintenance actions. |

### Finding devices on your network

*Devices on your network* in the main menu lists the DLNA/UPnP **MediaRenderer**
devices it can see — most smart TVs advertise themselves as one. Each entry
shows the device's manufacturer, model and IP address.

Discovery is a standard SSDP search: a multicast `M-SEARCH` to
`239.255.255.250:1900`, then a fetch of each responder's device description to
read its name and service list. Only devices exposing an `AVTransport` service
are listed, which keeps printers, routers and NAS boxes out of the results.

Results are remembered for a few minutes (configurable) so browsing back into
the folder is instant; *Scan again* forces a fresh search. If a device you
expect is missing:

- It may be powered off or have "network standby" / "wake on network" disabled.
- The device must be on the **same subnet** — the search goes out over the
  host's default multicast interface, so an active VPN or a second NIC can send
  it to the wrong network.
- Some routers block or rate-limit multicast between clients; look for an
  "IGMP snooping" or "AP isolation" setting.
- On a slow or busy network, raise the discovery timeout in settings.

### Casting to a TV

Pick **Play on device…** from any item's context menu. If exactly one renderer
is known it is used straight away; otherwise you choose from a list. The
device's context menu in *Devices on your network* has **Playback controls**
for pause / resume / stop.

**Nothing streams through Kodi.** DLNA casting hands the TV a URL and tells it
to play; the TV then downloads the video *itself*, directly from your content
source. That has two consequences worth understanding:

- **The stream URL must be reachable from the TV**, over plain `http://` or
  `https://`. A URL that only Kodi can resolve — a `plugin://` URL, a local
  file, a host that only resolves on Kodi's machine — is rejected before
  anything is sent. If your backend serves from `localhost`, the TV cannot
  reach it; bind it to a LAN address instead.
- **Playback outlives the add-on.** Once the TV is playing, Kodi is out of the
  loop; closing it will not stop the video. Use *Playback controls* to stop it.

Progressive streams (MP4/MKV) are strongly preferred, since the TV plays the
URL with no InputStream Adapter in the path. If a source only offers an
HLS/DASH manifest the add-on asks before trying — some TVs handle HLS
natively, many do not. When a device refuses an item it reports a UPnP error
code, which the add-on surfaces verbatim: `714` means it rejected the format,
`716` means it could not download the URL, `701` means it was busy.

## Installation

1. Copy the `plugin.video.cumnation` folder into your Kodi `addons` directory,
   **or** zip it and install via *Add-ons → Install from zip file*.
2. Enable the add-on and open its **Settings**.
3. Set **Base API URL** to your content source (see the contract below).

## Content source contract

The add-on talks to a JSON API. Point **Base API URL** at the root; all paths
are relative to it.

```
GET {base}/categories
    -> {"categories": [{"id","name","url","thumb","plot","count"}, ...]}

GET {base}/list?category={id}&page={n}&limit={size}
    -> {"videos": [<video>...], "page": n, "has_next": bool}

GET {base}/search?q={query}&page={n}&limit={size}
    -> {"videos": [<video>...], "page": n, "has_next": bool}

GET {base}/resolve?id={video_id}[&url={page_url}]
    # single progressive stream:
    -> {"stream": "https://.../file.mp4", "headers": {...}}
    # or multiple / adaptive / DRM-protected streams:
    -> {"streams": [<stream>, ...]}

<video>  = {"id","title","url","thumb","preview","plot",
            "duration","date","rating","tags"}

 ``preview`` is an optional URL to a preview image (a still or
 animated frame from the video). When present it is shown as
 the listing's background image; ``thumb`` is always used for
 the poster/thumbnail.

<stream> = {"url",                       # required
            "quality",                   # vertical resolution, e.g. 1080
            "label",                     # optional display label
            "headers",                   # optional request headers
            "manifest_type",             # "hls" | "mpd" | "ism" -> InputStream Adapter
            "mime_type",                 # optional, e.g. "application/dash+xml"
            "license_type",              # optional DRM, e.g. "com.widevine.alpha"
            "license_key",               # optional ISA license key string
            "subtitle",                  # optional single subtitle URL
            "subtitles"}                 # optional list, for multiple languages:
                                          #   ["https://.../movie.en.vtt", ...] or
                                          #   [{"url": "...", "language": "en"}, ...]
```

`subtitles` (plural) is a list — one URL per language track; `subtitle`
(singular) is a shorthand for one. Kodi has no separate parameter for a
track's language: name each file with a language code (`movie.en.vtt`,
`movie.fr.vtt`) and Kodi's own subtitle picker reads it from the filename;
`"language"` in a `{"url", "language"}` entry is metadata for your own
tooling, not something Kodi consumes directly.

Both `/resolve` shapes are supported; a plain `{"stream": ...}` still works.
`headers` are applied as Kodi request headers (progressive) or ISA
`stream_headers` (adaptive) — e.g. for `Referer`/`User-Agent`-gated CDNs.
When several streams are returned, the **Preferred quality** setting decides
which plays (or prompts).

### Static sources (no server, free)

If you don't want to run or pay for anything, turn on **This is a static
source (no server)** in Settings alongside the Base API URL (or when adding
a named source). Requests become fixed file paths instead of query strings,
so a plain file host — GitHub Pages, S3, a gist, anything that serves files
over HTTP — is enough; there is no code to run and nothing to keep online:

```
GET {base}/categories.json
GET {base}/list/{category}/{page}.json
GET {base}/resolve/{id}.json
GET {base}/search-index.json          # optional, powers search
```

There's no server to run a search query against, so search instead fetches
`search-index.json` once (cached) — a flat `{"videos": [<video>...]}` list
of every video across every category — and filters it client-side by
title. It's optional: an older static source (or a hand-authored one)
without that file just returns no search results instead of erroring.

`tools/build_static_demo.py` bakes this repo's own demo catalogue into
that exact layout (search-index.json included); see **Try it without a
backend** below for a URL you can use right now. `tools/build_static_source.py`
does the same for a folder of your own videos — see **Build a static
source from your own files** below.

### Skin widgets

Bind these plugin paths as widgets in a skin:

```
plugin://plugin.video.cumnation/?action=widget&type=favorites
plugin://plugin.video.cumnation/?action=widget&type=history
plugin://plugin.video.cumnation/?action=widget&type=category&category=<id>
```

## Try it without a backend

**No computer, free, nothing to run:** this repo's GitHub Pages already
hosts a static copy of the demo catalogue (the same Creative-Commons
Blender movies below). Set **Base API URL** to
`https://deegan4.github.io/KodiCum/demo-content` and turn on **This is a
static source (no server)** — that's it, no accounts, no hosting to set up.

**Run it yourself instead:** a reference backend is included. It serves the
same Creative-Commons Blender open movies so you can exercise the whole
path — including playback — immediately:

```bash
python3 plugin.video.cumnation/resources/lib/mock_server.py 8080
# then set Base API URL to http://<your-ip>:8080 (leave "static" off)
```

`GET /` on the running server is a small status dashboard (uptime, request
log) — handy for checking it's up when it's running headless somewhere you
can't easily shell into, e.g. a TV box on Tailscale.

### Running it on an Android TV box (Termux)

To run the reference backend directly on a TV box via [Termux](https://termux.dev),
supervised so it survives the screen sleeping and restarts if it crashes, plus
`sshd` for remote administration:

```bash
pkg install -y curl && curl -sL \
  https://raw.githubusercontent.com/Deegan4/KodiCum/main/tools/termux_bootstrap.sh | sh
```

Then run `passwd` once to set an SSH login password (`tools/termux_bootstrap.sh`
does everything else, but a password can't be set non-interactively without
putting it in plaintext in the script). See the script's header comment for
what it does and the manual steps if you'd rather run them yourself.

The script also writes a [Termux:Boot](https://f-droid.org/packages/com.termux.boot/)
hook so the backend and `sshd` come back up automatically on every device
reboot -- install and launch **Termux:Boot** once (from F-Droid, nothing to
configure in the app itself) and the dashboard is reachable as soon as the box
powers on, no need to open Termux again. The Kodi add-on itself can't start
this directly -- it's a separate sandboxed Android app with no way to reach
into Termux -- so this is the OS-level equivalent: the backend is simply
always running rather than being launched by anything.

## Build a static source from your own files

`tools/build_static_source.py` is the same idea as the demo above, but for
your own videos instead of Big Buck Bunny -- no server to run, no account,
just files you upload somewhere:

```
media/
    Featured/
        Big Buck Bunny.mp4
        Big Buck Bunny.jpg          # optional thumb (same base name)
        Big Buck Bunny.en.vtt       # optional subtitle (language in the name)
    Home Movies/
        beach_trip.mkv
```

```bash
python3 tools/build_static_source.py media/ out/ --base-url https://example.com/mysource
```

Each top-level folder becomes a category, each video file inside it a video;
a same-named image is its thumbnail and same-named `.vtt`/`.srt` files are
subtitles (one per language, named `<video>.<lang>.vtt`). `out/` ends up
holding both the generated JSON *and* copies of your media files, so
uploading that one folder to any static host (GitHub Pages on a repo of
your own, Netlify, S3, a NAS's web server, ...) is enough. `--base-url` is
required: it's the URL `out/` will be served from once uploaded, baked into
every stream/thumb/subtitle URL.

Then in the add-on: **Base API URL** = your base URL, **This is a static
source (no server)** = on.

## Development

```bash
# byte-compile everything
python3 -m compileall plugin.video.cumnation

# run the off-device unit tests (Kodi is stubbed, no install needed)
python3 -m unittest discover -s tests
```

### Layout

```
plugin.video.cumnation/
├── addon.py                     # entry point (thin launcher)
├── addon.xml                    # add-on metadata & dependencies
└── resources/
    ├── settings.xml             # settings UI
    ├── language/…/strings.po    # localized strings
    └── lib/
        ├── router.py            # URL routing + directory building
        ├── content.py           # JSON content-source client
        ├── models.py            # Category / Video / Stream / Renderer / Page
        ├── dlna.py              # DLNA/UPnP renderer discovery (SSDP)
        ├── cast.py              # casting + transport control (AVTransport)
        ├── favorites.py         # favorites store
        ├── history.py           # search + watch history
        ├── resume.py            # resume points
        ├── player.py            # playback monitor for resume
        ├── storage.py           # JSON persistence
        ├── kodiutils.py         # Kodi API wrappers
        └── mock_server.py       # reference backend (not loaded by Kodi)
```

## Content responsibility

This add-on ships **no content and no scrapers** for any third-party site. You
are responsible for the source you connect it to and for complying with that
source's terms and with applicable law in your jurisdiction.

## License

MIT — see [LICENSE.txt](LICENSE.txt).
