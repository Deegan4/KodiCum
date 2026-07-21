# -*- coding: utf-8 -*-
"""Search history and watch history, persisted as JSON in the profile.

Both are capped so the files stay small and the most recent entries surface
first.
"""
from . import storage
from . import kodiutils
from .models import Video

SEARCH_STORE = 'search_history.json'
WATCH_STORE = 'watch_history.json'


def _limit():
    return max(1, kodiutils.get_setting_int('history_size', 50))


# -- Search history -------------------------------------------------------
def search_terms():
    return storage.load(SEARCH_STORE, default=[])


def add_search(term):
    term = (term or '').strip()
    if not term:
        return
    terms = [t for t in search_terms() if t.lower() != term.lower()]
    terms.insert(0, term)
    storage.save(SEARCH_STORE, terms[:_limit()])


def remove_search(term):
    terms = [t for t in search_terms() if t != term]
    storage.save(SEARCH_STORE, terms)


def clear_search():
    storage.save(SEARCH_STORE, [])


# -- Watch history --------------------------------------------------------
def watched():
    return [Video.from_dict(item) for item in storage.load(WATCH_STORE, default=[])]


def add_watched(video):
    if not kodiutils.get_setting_bool('track_history', True):
        return
    items = [item for item in storage.load(WATCH_STORE, default=[])
             if item.get('id') != video.id]
    items.insert(0, video.to_dict())
    storage.save(WATCH_STORE, items[:_limit()])


def clear_watched():
    storage.save(WATCH_STORE, [])
