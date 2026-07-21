# -*- coding: utf-8 -*-
"""User favorites, persisted as JSON in the add-on profile."""
from . import storage
from .models import Video

STORE = 'favorites.json'


def _load():
    return storage.load(STORE, default=[])


def all_favorites():
    return [Video.from_dict(item) for item in _load()]


def is_favorite(video_id):
    return any(item.get('id') == video_id for item in _load())


def add(video):
    items = _load()
    if any(item.get('id') == video.id for item in items):
        return False
    items.insert(0, video.to_dict())
    storage.save(STORE, items)
    return True


def remove(video_id):
    items = _load()
    filtered = [item for item in items if item.get('id') != video_id]
    if len(filtered) == len(items):
        return False
    storage.save(STORE, filtered)
    return True


def toggle(video):
    if is_favorite(video.id):
        remove(video.id)
        return False
    add(video)
    return True


def clear():
    storage.save(STORE, [])
