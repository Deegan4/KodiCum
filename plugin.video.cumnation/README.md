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

<video>  = {"id","title","url","thumb","plot","duration",
            "date","rating","tags"}

<stream> = {"url",                       # required
            "quality",                   # vertical resolution, e.g. 1080
            "label",                     # optional display label
            "headers",                   # optional request headers
            "manifest_type",             # "hls" | "mpd" | "ism" -> InputStream Adapter
            "mime_type",                 # optional, e.g. "application/dash+xml"
            "license_type",              # optional DRM, e.g. "com.widevine.alpha"
            "license_key"}               # optional ISA license key string
```

Both `/resolve` shapes are supported; a plain `{"stream": ...}` still works.
`headers` are applied as Kodi request headers (progressive) or ISA
`stream_headers` (adaptive) — e.g. for `Referer`/`User-Agent`-gated CDNs.
When several streams are returned, the **Preferred quality** setting decides
which plays (or prompts).

### Skin widgets

Bind these plugin paths as widgets in a skin:

```
plugin://plugin.video.cumnation/?action=widget&type=favorites
plugin://plugin.video.cumnation/?action=widget&type=history
plugin://plugin.video.cumnation/?action=widget&type=category&category=<id>
```

## Try it without a backend

A reference backend is included. It serves Creative-Commons Blender open movies
so you can exercise the whole path — including playback — immediately:

```bash
python3 plugin.video.cumnation/resources/lib/mock_server.py 8080
# then set Base API URL to http://<your-ip>:8080
```

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
