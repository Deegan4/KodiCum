# -*- coding: utf-8 -*-
"""Simple JSON-backed persistence stored in the add-on profile directory.

Used for favorites, search history and watch history. Each store is a small
JSON file; concurrent writes from a single Kodi add-on are not a concern.
"""
import json
import os

import xbmcvfs

from . import kodiutils


def _profile_dir():
    profile = kodiutils.ADDON_PROFILE
    if not xbmcvfs.exists(profile):
        xbmcvfs.mkdirs(profile)
    return profile


def _path(name):
    return os.path.join(_profile_dir(), name)


def load(name, default=None):
    """Load a JSON file from the profile dir, returning default on any error."""
    path = _path(name)
    if not xbmcvfs.exists(path):
        return default if default is not None else []
    try:
        with xbmcvfs.File(path) as handle:
            content = handle.read()
        return json.loads(content) if content else (default if default is not None else [])
    except (ValueError, IOError) as exc:
        kodiutils.log_error('Failed to load {0}: {1}'.format(name, exc))
        return default if default is not None else []


def save(name, data):
    """Write data as JSON to the profile dir. Returns True on success."""
    path = _path(name)
    try:
        with xbmcvfs.File(path, 'w') as handle:
            handle.write(json.dumps(data, ensure_ascii=False, indent=2))
        return True
    except (TypeError, IOError) as exc:
        kodiutils.log_error('Failed to save {0}: {1}'.format(name, exc))
        return False
