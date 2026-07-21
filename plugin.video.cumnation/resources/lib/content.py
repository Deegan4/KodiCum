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
         -> {"stream": "https://.../file.mp4", "headers": {...}}

    where <video> = {"id","title","url","thumb","plot","duration",
                     "date","rating","tags"}

If you already have a Kodi-friendly backend, this is all you need to wire up.
"""
import json

try:
    from urllib.parse import urlencode
except ImportError:  # pragma: no cover - Python 2 fallback
    from urllib import urlencode

import requests

from . import kodiutils
from .models import Category, Video, Page

DEFAULT_TIMEOUT = 20


class ContentError(Exception):
    """Raised when the content source cannot fulfil a request."""


class ContentSource(object):
    def __init__(self):
        self.base_url = kodiutils.get_setting('base_url').rstrip('/')
        self.page_size = kodiutils.get_setting_int('page_size', 30)
        self.session = requests.Session()
        user_agent = kodiutils.get_setting(
            'user_agent',
            'Mozilla/5.0 (Kodi) Cumnation/1.0',
        )
        self.session.headers.update({'User-Agent': user_agent})

    # -- HTTP helpers -----------------------------------------------------
    def _get(self, path, params=None):
        if not self.base_url:
            raise ContentError(kodiutils.get_string(32050))  # "Configure a content source"
        url = '{0}/{1}'.format(self.base_url, path.lstrip('/'))
        if params:
            url = '{0}?{1}'.format(url, urlencode(params))
        kodiutils.log('GET {0}'.format(url))
        try:
            response = self.session.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            kodiutils.log_error('Request failed: {0}'.format(exc))
            raise ContentError(str(exc))
        except ValueError as exc:
            kodiutils.log_error('Invalid JSON from source: {0}'.format(exc))
            raise ContentError('Invalid response from content source')

    # -- Public API -------------------------------------------------------
    def categories(self):
        data = self._get('categories')
        return [Category.from_dict(item) for item in data.get('categories', [])]

    def list_videos(self, category_id, page=1):
        params = {'category': category_id, 'page': page, 'limit': self.page_size}
        data = self._get('list', params)
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
        """Return (stream_url, headers) for a playable item.

        A source may return a direct stream URL right away, or point at a
        page URL that needs a second resolve step. We keep it simple: ask the
        API for the stream.
        """
        params = {'id': video_id}
        if video_url:
            params['url'] = video_url
        data = self._get('resolve', params)
        stream = data.get('stream')
        if not stream:
            raise ContentError('No playable stream returned')
        return stream, data.get('headers', {})
