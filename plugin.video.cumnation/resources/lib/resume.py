# -*- coding: utf-8 -*-
"""Resume-point tracking.

Kodi does not persist resume positions for plugin items automatically, so we
store them ourselves keyed by video id. A background player monitor samples
the position during playback and writes the last point when playback stops.
"""
from . import storage
from . import kodiutils

STORE = 'resume.json'
# Below this fraction we treat the item as "not really started"; above the
# finished threshold we clear the resume point so it plays from the start.
MIN_SECONDS = 10
FINISHED_FRACTION = 0.95


def _load():
    return storage.load(STORE, default={})


def get(video_id):
    """Return saved position in seconds for a video, or 0."""
    entry = _load().get(str(video_id))
    return float(entry.get('position', 0)) if entry else 0.0


def set(video_id, position, total):
    data = _load()
    key = str(video_id)
    if total and position >= total * FINISHED_FRACTION:
        data.pop(key, None)
    elif position >= MIN_SECONDS:
        data[key] = {'position': round(float(position), 1),
                     'total': round(float(total or 0), 1)}
    else:
        return
    storage.save(STORE, data)


def clear(video_id=None):
    if video_id is None:
        storage.save(STORE, {})
        return
    data = _load()
    if data.pop(str(video_id), None) is not None:
        storage.save(STORE, data)


def enabled():
    return kodiutils.get_setting_bool('resume_playback', True)
