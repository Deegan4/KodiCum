# -*- coding: utf-8 -*-
"""Plain data objects passed between the content source and the UI layer.

Keeping these as explicit classes (rather than raw dicts) gives the router a
stable contract regardless of which content source produced them.
"""


class Category(object):
    """A browsable node: a genre, tag, channel or sub-listing."""

    def __init__(self, cid, name, url=None, thumb=None, plot=None, count=None):
        self.id = cid
        self.name = name
        self.url = url
        self.thumb = thumb
        self.plot = plot
        self.count = count

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'thumb': self.thumb,
            'plot': self.plot,
            'count': self.count,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            cid=data.get('id'),
            name=data.get('name', ''),
            url=data.get('url'),
            thumb=data.get('thumb'),
            plot=data.get('plot'),
            count=data.get('count'),
        )


class Video(object):
    """A playable item."""

    def __init__(self, vid, title, url=None, thumb=None, plot=None,
                 duration=None, date=None, rating=None, tags=None):
        self.id = vid
        self.title = title
        self.url = url
        self.thumb = thumb
        self.plot = plot
        self.duration = duration          # seconds
        self.date = date                  # 'dd.mm.yyyy'
        self.rating = rating              # float 0-10
        self.tags = tags or []

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'thumb': self.thumb,
            'plot': self.plot,
            'duration': self.duration,
            'date': self.date,
            'rating': self.rating,
            'tags': self.tags,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            vid=data.get('id'),
            title=data.get('title', ''),
            url=data.get('url'),
            thumb=data.get('thumb'),
            plot=data.get('plot'),
            duration=data.get('duration'),
            date=data.get('date'),
            rating=data.get('rating'),
            tags=data.get('tags') or [],
        )


class Stream(object):
    """A single playable rendition of a video.

    A source may return several (e.g. 1080p/720p/480p, or an adaptive
    manifest). ``manifest_type`` (hls/mpd/ism) signals adaptive streaming via
    InputStream Adapter; ``license_type``/``license_key`` carry optional DRM.
    """

    def __init__(self, url, quality=0, label=None, headers=None,
                 manifest_type=None, mime_type=None,
                 license_type=None, license_key=None):
        self.url = url
        self.quality = int(quality or 0)     # vertical resolution, e.g. 1080
        self.label = label
        self.headers = headers or {}
        self.manifest_type = manifest_type   # 'hls' | 'mpd' | 'ism' | None
        self.mime_type = mime_type
        self.license_type = license_type     # e.g. 'com.widevine.alpha'
        self.license_key = license_key

    @property
    def is_adaptive(self):
        return bool(self.manifest_type)

    @property
    def display_label(self):
        if self.label:
            return self.label
        if self.quality:
            return '{0}p'.format(self.quality)
        return 'Default'

    @classmethod
    def from_dict(cls, data):
        return cls(
            url=data.get('url') or data.get('stream'),
            quality=data.get('quality', 0),
            label=data.get('label'),
            headers=data.get('headers') or {},
            manifest_type=data.get('manifest_type'),
            mime_type=data.get('mime_type'),
            license_type=data.get('license_type'),
            license_key=data.get('license_key'),
        )


def select_stream(streams, preference):
    """Choose a stream given a preference.

    ``preference`` is 0 for "highest quality", or a target vertical
    resolution (e.g. 720). Returns the best stream at or below the target,
    or the highest available if none qualify. ``streams`` must be non-empty.
    """
    if len(streams) == 1:
        return streams[0]
    ordered = sorted(streams, key=lambda s: s.quality, reverse=True)
    if not preference:
        return ordered[0]
    at_or_below = [s for s in ordered if s.quality and s.quality <= preference]
    return at_or_below[0] if at_or_below else ordered[0]


class Page(object):
    """A page of results plus a flag telling the UI whether more exist."""

    def __init__(self, items, page=1, has_next=False):
        self.items = items
        self.page = page
        self.has_next = has_next
