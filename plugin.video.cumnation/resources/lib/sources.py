# -*- coding: utf-8 -*-
"""Content source management.

Supports multiple configured content sources with one active at a time.
Sources are stored in a JSON file in the add-on profile; the active
source ID determines which URL the content client connects to.
"""
import json

from . import storage
from . import kodiutils

STORE = 'sources.json'
DEFAULT_SOURCE_ID = 'default'


def _load():
    data = storage.load(STORE, default=None)
    if data is None:
        data = {
            'sources': [{
                'id': DEFAULT_SOURCE_ID,
                'name': 'Content Source',
                'url': '',
            }],
            'active': DEFAULT_SOURCE_ID,
        }
        storage.save(STORE, data)
    return data


def all_sources():
    """Return the list of configured sources."""
    return _load().get('sources', [])


def active_source():
    """Return the currently active source dict."""
    sources = all_sources()
    active_id = _load().get('active')
    for s in sources:
        if s.get('id') == active_id:
            return s
    return sources[0] if sources else {'id': DEFAULT_SOURCE_ID,
                                       'name': 'Content Source', 'url': ''}


def active_url():
    """Return the URL of the active source."""
    return active_source().get('url', '')


def active_is_static():
    """Whether the active source is a static (serverless) file host."""
    return bool(active_source().get('static', False))


def set_active(source_id):
    """Switch the active source by ID."""
    data = _load()
    data['active'] = source_id
    storage.save(STORE, data)


def add_source(name, url, static=False):
    """Add a new content source.

    ``static`` marks a source hosted on a plain file host (no server-side
    logic, e.g. GitHub Pages) that serves the JSON API contract as static
    files instead of answering query strings; see ``content.py``.
    """
    data = _load()
    source_id = 'source{0}'.format(len(data['sources']))
    source = {'id': source_id, 'name': name, 'url': url, 'static': bool(static)}
    data['sources'].append(source)
    data['active'] = source_id
    storage.save(STORE, data)
    return source_id


def remove_source(source_id):
    """Remove a content source by ID."""
    data = _load()
    data['sources'] = [s for s in data['sources']
                       if s.get('id') != source_id]
    if data['active'] == source_id:
        data['active'] = data['sources'][0]['id'] if data['sources'] \
            else DEFAULT_SOURCE_ID
    storage.save(STORE, data)


def rename_source(source_id, name):
    for s in all_sources():
        if s.get('id') == source_id:
            s['name'] = name
    storage.save(STORE, _load())


def clear():
    storage.save(STORE, {
        'sources': [{
            'id': DEFAULT_SOURCE_ID,
            'name': 'Content Source',
            'url': '',
        }],
        'active': DEFAULT_SOURCE_ID,
    })
