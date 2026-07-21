# -*- coding: utf-8 -*-
"""TTL cache for content-source responses, persisted in the add-on profile.

Navigating back and forth in Kodi re-invokes the add-on and would otherwise
re-hit the network every time. This caches JSON responses for a configurable
number of minutes. Entries are keyed by request signature and carry a stored
timestamp; expired or disabled entries simply miss.
"""
import time

from . import storage
from . import kodiutils

STORE = 'http_cache.json'


def ttl_seconds():
    return max(0, kodiutils.get_setting_int('cache_ttl', 10)) * 60


def enabled():
    return ttl_seconds() > 0


def _load():
    return storage.load(STORE, default={})


def get(key, now=None):
    """Return a cached value for key, or None if missing/expired/disabled."""
    if not enabled():
        return None
    entry = _load().get(key)
    if not entry:
        return None
    now = time.time() if now is None else now
    if now - entry.get('ts', 0) > ttl_seconds():
        return None
    return entry.get('value')


def set(key, value, now=None):
    if not enabled():
        return
    data = _load()
    data[key] = {'ts': time.time() if now is None else now, 'value': value}
    storage.save(STORE, data)


def clear():
    storage.save(STORE, {})
