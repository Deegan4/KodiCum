#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bake the sample catalogue into a static, serverless content source.

Produces ``repo/zips/demo-content/`` as plain JSON files matching the
layout ``content.py`` requests when a source is marked "static": no
server-side logic needed, so it can be hosted for free on GitHub Pages (or
any plain file host) alongside the Kodi repository itself, at

    https://deegan4.github.io/KodiCum/demo-content/

Point the add-on's Base API URL at that address and enable "This is a
static source (no server)" in Settings -> Content Source. Everything in
``mock_server.py``'s demo catalogue works, including the quality picker
and (via the pre-baked search-index.json) search.

Run *after* ``tools/build_repo.py`` (which wipes and rebuilds ``repo/zips/``
from scratch) and re-run whenever ``resources/lib/demo_content.py`` changes:

    python3 tools/build_repo.py
    python3 tools/build_static_demo.py
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, 'repo', 'zips', 'demo-content')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_repo  # noqa: E402 - reuse its Kodi-browsable index.html writer

sys.path.insert(0, os.path.join(
    ROOT, 'plugin.video.cumnation', 'resources', 'lib'))
import demo_content  # noqa: E402


def _write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write('\n')


def main():
    zips_dir = os.path.dirname(OUTPUT)
    if not os.path.isdir(zips_dir):
        raise SystemExit('{0}/ not found - run tools/build_repo.py first'
                          .format(os.path.relpath(zips_dir, ROOT)))

    if os.path.isdir(OUTPUT):
        shutil.rmtree(OUTPUT)

    _write_json(os.path.join(OUTPUT, 'categories.json'),
                {'categories': demo_content.CATEGORIES})

    for category_id, videos in demo_content.VIDEOS.items():
        # Only page 1 exists: has_next is always false, so the add-on never
        # requests a page 2 for this small, fixed demo catalogue.
        _write_json(
            os.path.join(OUTPUT, 'list', category_id, '1.json'),
            {'videos': videos, 'page': 1, 'has_next': False})

    seen = set()
    unique_videos = []
    for items in demo_content.VIDEOS.values():
        for video in items:
            _write_json(
                os.path.join(OUTPUT, 'resolve', '{0}.json'.format(video['id'])),
                demo_content.resolve_payload(video['id']))
            if video['id'] not in seen:  # a video may appear in >1 category
                seen.add(video['id'])
                unique_videos.append(video)

    _write_json(os.path.join(OUTPUT, 'search-index.json'),
                {'videos': unique_videos})

    for base, _dirs, _files in os.walk(OUTPUT):
        build_repo.write_index(base)

    print('wrote static demo content to {0}'.format(
        os.path.relpath(OUTPUT, ROOT)))


if __name__ == '__main__':
    main()
