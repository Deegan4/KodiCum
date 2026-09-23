# KodiCum

Home of **Cumnation**, a configurable video add-on for [Kodi](https://kodi.tv).

The add-on lives in [`plugin.video.cumnation/`](plugin.video.cumnation/). It
provides category browsing, search with history, favorites, watch history and
resume support on top of a JSON content source you configure — it ships the
framework, not the content.

- **Add-on & docs:** [`plugin.video.cumnation/README.md`](plugin.video.cumnation/README.md)
- **Try it instantly:** a reference backend serving Creative-Commons Blender
  movies is included (`resources/lib/mock_server.py`).

## Install in Kodi (as a repository source)

This repo is a self-contained Kodi repository, so Kodi can install and
auto-update the add-on. In Kodi:

1. **Settings → System → Add-ons** and enable **Unknown sources**.
2. **Settings → File manager → Add source** and enter this URL:

   ```
   https://deegan4.github.io/KodiCum/
   ```

   Give it a name such as `Cumnation` and select **OK**.

   > Don't use a `raw.githubusercontent.com` URL here. Raw GitHub can't list
   > directories, so Kodi fails with *"Couldn't retrieve directory
   > information… network not connected"*. The GitHub Pages URL above serves
   > the browsable listings Kodi needs.
3. **Settings → Add-ons → Install from zip file** → pick the source you just
   added → `repository.cumnation` → `repository.cumnation-1.0.0.zip`.
4. **Install from repository → Cumnation Repository → Video add-ons →
   Cumnation → Install.**
5. Open **Cumnation → Settings** and set the **Base API URL** to your content
   source (see the [add-on README](plugin.video.cumnation/README.md)).

From then on Kodi keeps the add-on updated from this repository automatically.

### Publishing the source (one-time)

The source URL is served by GitHub Pages via
[`.github/workflows/pages.yml`](.github/workflows/pages.yml), which publishes
`repo/zips/` on every push to `main`. Enable it once under **Settings → Pages →
Build and deployment → Source: GitHub Actions**, then re-run the *Publish Kodi
source* workflow (or push to `main`).

If Kodi still says it couldn't retrieve directory information, open
`https://deegan4.github.io/KodiCum/` in a browser first — if that doesn't show
a file listing, Pages isn't enabled yet. If it does, check the Kodi device's
own network connection and that the URL was typed exactly.

### Rebuilding the repository

The `repo/` tree is generated — do not edit it by hand. After changing an
add-on (or bumping its `version` in `addon.xml`), regenerate it:

```bash
python3 tools/build_repo.py
```

## Quick start

```bash
# run the tests (Kodi is stubbed, nothing to install)
python3 -m unittest discover -s tests

# start the reference backend, then set the add-on's Base API URL to it
python3 plugin.video.cumnation/resources/lib/mock_server.py 8080
```

Requires Kodi 19+ (Python 3). Licensed under the MIT License.
