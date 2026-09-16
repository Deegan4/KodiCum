# -*- coding: utf-8 -*-
"""Trakt.tv scrobbling.

Sends watch progress events to Trakt so viewing is tracked
across devices. Requires a Trakt account, API token, and per-video
``trakt_id`` supplied by the content source.

Events sent:
- ``start``    : playback began (after stream resolution)
- ``stop``     : playback stopped at a specific position
- ``completed``: playback finished (>95% of total duration)
"""
import datetime
import json

from . import kodiutils

API_URL = 'https://api.trakt.tv'
TIMEOUT = 10


def _requests():
    import requests
    return requests


def enabled():
    return kodiutils.get_setting_bool('trakt_enabled', False)


def _headers():
    token = kodiutils.get_setting('trakt_api_token')
    username = kodiutils.get_setting('trakt_username')
    return {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': token,
        'Authorization': 'Bearer {0}'.format(token),
    }


def _url(path):
    return '{0}{1}'.format(API_URL, path)


def _post(path, payload):
    try:
        requests = _requests()
        response = requests.post(_url(path),
                                  headers=_headers(),
                                  json=payload,
                                  timeout=TIMEOUT)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        kodiutils.log_error('Trakt {0}: {1}'.format(path, exc))
        return False


def scrobble_start(video):
    """Signal that playback of ``video`` has started."""
    if not enabled():
        return
    if not getattr(video, 'trakt_id', None):
        return
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
    if getattr(video, 'trakt_type', 'movie') == 'show':
        payload = {
            'shows': [{
                'ids': {'trakt': video.trakt_id},
                'started_at': ts,
            }],
        }
        _post('/sync/playback/start', payload)
    else:
        payload = {
            'movies': [{
                'ids': {'trakt': video.trakt_id},
                'started_at': ts,
            }],
        }
        _post('/sync/playback/start', payload)


def scrobble_stop(video, position):
    """Signal that playback of ``video`` stopped at ``position`` seconds."""
    if not enabled():
        return
    if not getattr(video, 'trakt_id', None):
        return
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
    duration = max(int(video.duration or 0), 1)
    percent = min(int(position / duration * 100), 100)
    if getattr(video, 'trakt_type', 'movie') == 'show':
        payload = {
            'shows': [{
                'ids': {'trakt': video.trakt_id},
                'progress': int(position),
                'percent': percent,
                'stopped_at': ts,
            }],
        }
        _post('/sync/playback/stop', payload)
    else:
        payload = {
            'movies': [{
                'ids': {'trakt': video.trakt_id},
                'progress': int(position),
                'percent': percent,
                'stopped_at': ts,
            }],
        }
        _post('/sync/playback/stop', payload)


def scrobble_complete(video):
    """Signal that ``video`` was fully watched."""
    if not enabled():
        return
    if not getattr(video, 'trakt_id', None):
        return
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
    if getattr(video, 'trakt_type', 'movie') == 'show':
        payload = {
            'shows': [{
                'ids': {'trakt': video.trakt_id},
                'completed_at': ts,
            }],
        }
        _post('/sync/playback/completed', payload)
    else:
        payload = {
            'movies': [{
                'ids': {'trakt': video.trakt_id},
                'completed_at': ts,
            }],
        }
        _post('/sync/playback/completed', payload)
