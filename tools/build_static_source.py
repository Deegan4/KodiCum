#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Turn a folder of your own videos into a static, serverless content source.

Same idea as ``build_static_demo.py`` (see its docstring and the README's
"Static sources" section for the contract this produces) but for your own
files instead of the built-in demo catalogue. No account, API key or server
required — the output is plain files you upload anywhere that serves HTTP
(GitHub Pages, Netlify, S3, a gist, ...).

Point it at a folder shaped like:

    media/
        Featured/
            Big Buck Bunny.mp4
            Big Buck Bunny.jpg          # optional thumb (same basename)
            Big Buck Bunny.en.vtt       # optional subtitle (language in the name)
        Home Movies/
            beach_trip.mkv

Each top-level subfolder becomes a category; each video file inside it
becomes a video. Run:

    python3 tools/build_static_source.py media/ out/ --base-url https://example.com/mysource

then upload ``out/`` (which includes copies of your media files) to any
static host, and set the add-on's Base API URL to that base URL with
"This is a static source (no server)" enabled.

``--base-url`` is required: it's baked into every file/stream URL, since
Kodi needs an absolute URL to play from, not a path relative to wherever
this ran.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time

try:
    from urllib.parse import quote
except ImportError:  # pragma: no cover - Python 2 fallback
    from urllib import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_repo  # noqa: E402 - reuse its Kodi-browsable index.html writer

VIDEO_EXTS = {'.mp4', '.mkv', '.webm', '.m4v', '.mov', '.avi'}
SUBTITLE_EXTS = {'.vtt', '.srt'}
THUMB_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}


def slugify(text):
    slug = re.sub(r'[^A-Za-z0-9]+', '-', text).strip('-').lower()
    return slug or 'x'


def prettify(stem):
    return re.sub(r'[_\-]+', ' ', stem).strip() or stem


def unique_slug(base, taken):
    slug = base
    n = 2
    while slug in taken:
        slug = '{0}-{1}'.format(base, n)
        n += 1
    taken.add(slug)
    return slug


def find_subtitles(stem, files_by_stem):
    """Sibling ``<stem>[.<lang>].vtt|srt`` files for a video named ``stem``."""
    subs = []
    for name in files_by_stem.get(stem, []):
        root, ext = os.path.splitext(name)
        if ext.lower() not in SUBTITLE_EXTS:
            continue
        lang = None
        prefix = stem + '.'
        if root.lower().startswith(prefix.lower()) and len(root) > len(prefix):
            lang = root[len(prefix):]
        subs.append({'url': name, 'language': lang} if lang
                    else {'url': name, 'language': None})
    return sorted(subs, key=lambda s: s['url'])


def find_thumb(stem, files_by_stem):
    for name in files_by_stem.get(stem, []):
        if os.path.splitext(name)[1].lower() in THUMB_EXTS:
            return name
    return None


def scan_category(category_dir):
    """List (stem -> [sibling filenames]) for every file directly in ``category_dir``."""
    by_stem = {}
    for name in sorted(os.listdir(category_dir)):
        if not os.path.isfile(os.path.join(category_dir, name)):
            continue
        stem = name.split('.', 1)[0]
        by_stem.setdefault(stem, []).append(name)
    return by_stem


def build_videos(category_dir, category_slug, base_url, taken_ids):
    files_by_stem = scan_category(category_dir)
    videos = []
    for name in sorted(os.listdir(category_dir)):
        path = os.path.join(category_dir, name)
        if not os.path.isfile(path):
            continue
        stem, ext = os.path.splitext(name)
        if ext.lower() not in VIDEO_EXTS:
            continue

        video_id = unique_slug('{0}-{1}'.format(category_slug, slugify(stem)),
                               taken_ids)
        thumb_name = find_thumb(stem, files_by_stem)
        subtitle_names = find_subtitles(stem, files_by_stem)
        mtime = os.path.getmtime(path)

        media_url = '{0}/media/{1}/{2}'.format(
            base_url, category_slug, quote(name))
        video = {
            'id': video_id,
            'title': prettify(stem),
            'url': media_url,
            'date': time.strftime('%d.%m.%Y', time.localtime(mtime)),
            'tags': [],
        }
        if thumb_name:
            video['thumb'] = '{0}/media/{1}/{2}'.format(
                base_url, category_slug, quote(thumb_name))
        video['_source_path'] = path            # internal: for copying
        video['_thumb_source'] = (os.path.join(category_dir, thumb_name)
                                  if thumb_name else None)
        video['_subtitles'] = [
            {'url': '{0}/media/{1}/{2}'.format(
                 base_url, category_slug, quote(s['url'])),
             'language': s['language'],
             '_source': os.path.join(category_dir, s['url'])}
            for s in subtitle_names
        ]
        videos.append(video)
    return videos


def _public_video(video):
    """Strip the internal ``_*`` bookkeeping keys before writing JSON."""
    clean = {k: v for k, v in video.items() if not k.startswith('_')}
    if video['_subtitles']:
        clean['subtitles'] = [{'url': s['url'], 'language': s['language']}
                              for s in video['_subtitles']]
    return clean


def _write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write('\n')


def build(media_dir, output_dir, base_url):
    base_url = base_url.rstrip('/')
    if os.path.isdir(output_dir):
        shutil.rmtree(output_dir)

    categories = []
    all_videos = []
    taken_category_slugs = set()
    taken_ids = set()

    for name in sorted(os.listdir(media_dir)):
        category_dir = os.path.join(media_dir, name)
        if not os.path.isdir(category_dir):
            continue
        slug = unique_slug(slugify(name), taken_category_slugs)
        videos = build_videos(category_dir, slug, base_url, taken_ids)
        if not videos:
            continue  # skip empty folders rather than publish an empty category

        categories.append({'id': slug, 'name': prettify(name), 'count': len(videos)})
        _write_json(os.path.join(output_dir, 'list', slug, '1.json'),
                    {'videos': [_public_video(v) for v in videos],
                     'page': 1, 'has_next': False})

        for video in videos:
            resolve_payload = {'stream': video['url']}
            if video['_subtitles']:
                resolve_payload['subtitles'] = [
                    {'url': s['url'], 'language': s['language']}
                    for s in video['_subtitles']]
            _write_json(os.path.join(output_dir, 'resolve',
                                     '{0}.json'.format(video['id'])),
                       resolve_payload)

            dest = os.path.join(output_dir, 'media', slug,
                                os.path.basename(video['_source_path']))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(video['_source_path'], dest)
            if video['_thumb_source']:
                shutil.copy2(video['_thumb_source'],
                            os.path.join(output_dir, 'media', slug,
                                        os.path.basename(video['_thumb_source'])))
            for sub in video['_subtitles']:
                shutil.copy2(sub['_source'],
                            os.path.join(output_dir, 'media', slug,
                                        os.path.basename(sub['_source'])))

            all_videos.append(video)

    _write_json(os.path.join(output_dir, 'categories.json'),
                {'categories': categories})
    _write_json(os.path.join(output_dir, 'search-index.json'),
                {'videos': [_public_video(v) for v in all_videos]})

    for base, _dirs, _files in os.walk(output_dir):
        build_repo.write_index(base, root=output_dir)

    return categories, all_videos


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('media_dir', help='Folder of category subfolders + videos')
    parser.add_argument('output_dir', help='Folder to write the static source into')
    parser.add_argument('--base-url', required=True,
                        help='Public URL output_dir will be served from')
    args = parser.parse_args()

    if not os.path.isdir(args.media_dir):
        raise SystemExit('{0} is not a directory'.format(args.media_dir))

    categories, videos = build(args.media_dir, args.output_dir, args.base_url)
    print('wrote {0} categories, {1} videos to {2}'.format(
        len(categories), len(videos), args.output_dir))


if __name__ == '__main__':
    main()
