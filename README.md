# KodiCum

Home of **Cumnation**, a configurable video add-on for [Kodi](https://kodi.tv).

The add-on lives in [`plugin.video.cumnation/`](plugin.video.cumnation/). It
provides category browsing, search with history, favorites, watch history and
resume support on top of a JSON content source you configure — it ships the
framework, not the content.

- **Add-on & docs:** [`plugin.video.cumnation/README.md`](plugin.video.cumnation/README.md)
- **Try it instantly:** a reference backend serving Creative-Commons Blender
  movies is included (`resources/lib/mock_server.py`).

## Quick start

```bash
# run the tests (Kodi is stubbed, nothing to install)
python3 -m unittest discover -s tests

# start the reference backend, then set the add-on's Base API URL to it
python3 plugin.video.cumnation/resources/lib/mock_server.py 8080
```

Requires Kodi 19+ (Python 3). Licensed under the MIT License.
