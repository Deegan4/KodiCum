# -*- coding: utf-8 -*-
"""Content source abstraction.

The add-on is deliberately content-source agnostic. Instead of hard-coding a
single website, it talks to a JSON API whose base URL the user configures in
the add-on settings. This keeps the add-on generic, testable, and easy to
point at your own backend.

Expected JSON API shape (all endpoints relative to the configured base URL):

    GET  {base}/categories
         -> {"categories": [{"id","name","url","thumb","plot","count"}, ...]}

    GET  {base}/list?category={id}&page={n}
         -> {"videos": [ <video> ... ], "has_next": true, "page": 2}

    GET  {base}/search?q={query}&page={n}
         -> {"videos": [ <video> ... ], "has_next": false, "page": 1}

    GET  {base}/resolve?id={video_id}
         -> single stream:
            {"stream": "https://.../file.mp4", "headers": {...}}
         -> or multiple / adaptive / DRM streams:
            {"streams": [
                {"url","quality","label","headers",
                 "manifest_type","mime_type","license_type","license_key"},
                ...]}

    where <video> = {"id","title","url","thumb","plot","duration",
                     "date","rating","tags"}

    manifest_type is "hls" | "mpd" | "ism" for adaptive streams (played via
    InputStream Adapter); license_type/license_key carry optional DRM.

If you already have a Kodi-friendly backend, this is all you need to wire up.
"""
import json
import time

try:
    from urllib.parse import urlencode
except ImportError:  # pragma: no cover - Python 2 fallback
    from urllib import urlencode

import requests

from . import kodiutils
from . import cache
from .models import Category, Video, Page, Stream

DEFAULT_TIMEOUT = 20


class ContentError(Exception):
    """Raised when the content source cannot fulfil a request."""


class ContentSource(object):
    def __init__(self):
        self.base_url = kodiutils.get_setting('base_url').rstrip('/')
        self.page_size = kodiutils.get_setting_int('page_size', 30)
        self.retries = max(0, kodiutils.get_setting_int('network_retries', 2))
        self.session = requests.Session()
        user_agent = kodiutils.get_setting(
            'user_agent',
            'Mozilla/5.0 (Kodi) Cumnation/1.0',
        )
        self.session.headers.update({'User-Agent': user_agent})

    # -- HTTP helpers -----------------------------------------------------
    def _request(self, url):
        """GET with retry/backoff on transient network errors."""
        last_exc = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    backoff = 2 ** attempt      # 1s, 2s, 4s, ...
                    kodiutils.log('Request failed ({0}), retry in {1}s'.format(
                        exc, backoff))
                    time.sleep(backoff)
                    continue
                kodiutils.log_error('Request failed: {0}'.format(exc))
                raise ContentError(str(exc))
            except ValueError as exc:
                kodiutils.log_error('Invalid JSON from source: {0}'.format(exc))
                raise ContentError('Invalid response from content source')
        raise ContentError(str(last_exc))       # pragma: no cover

    def _get(self, path, params=None, cacheable=False):
        if not self.base_url:
            raise ContentError(kodiutils.get_string(32050))  # "Configure a content source"
        url = '{0}/{1}'.format(self.base_url, path.lstrip('/'))
        if params:
            url = '{0}?{1}'.format(url, urlencode(params))

        if cacheable:
            hit = cache.get(url)
            if hit is not None:
                kodiutils.log('CACHE {0}'.format(url))
                return hit

        kodiutils.log('GET {0}'.format(url))
        data = self._request(url)

        if cacheable:
            cache.set(url, data)
        return data

    # -- Public API -------------------------------------------------------
    def categories(self):
        data = self._get('categories', cacheable=True)
        return [Category.from_dict(item) for item in data.get('categories', [])]

    def list_videos(self, category_id, page=1):
        params = {'category': category_id, 'page': page, 'limit': self.page_size}
        data = self._get('list', params, cacheable=True)
        videos = [Video.from_dict(item) for item in data.get('videos', [])]
        return Page(videos, page=data.get('page', page),
                    has_next=bool(data.get('has_next')))

    def search(self, query, page=1):
        params = {'q': query, 'page': page, 'limit': self.page_size}
        data = self._get('search', params)
        videos = [Video.from_dict(item) for item in data.get('videos', [])]
        return Page(videos, page=data.get('page', page),
                    has_next=bool(data.get('has_next')))

    def resolve(self, video_id, video_url=None):
        """Return a non-empty list of Stream objects for a playable item.

        Accepts either the single-stream shape ({"stream","headers"}) or the
        multi-stream shape ({"streams": [...]}), so older backends keep working.
        """
        params = {'id': video_id}
        if video_url:
            params['url'] = video_url
        data = self._get('resolve', params)

        streams = []
        if data.get('streams'):
            streams = [Stream.from_dict(s) for s in data['streams'] if s.get('url')]
        elif data.get('stream'):
            streams = [Stream(url=data['stream'], headers=data.get('headers', {}),
                              manifest_type=data.get('manifest_type'),
                              mime_type=data.get('mime_type'),
                              license_type=data.get('license_type'),
                              license_key=data.get('license_key'))]

        if not streams:
            raise ContentError('No playable stream returned')
        return streams
