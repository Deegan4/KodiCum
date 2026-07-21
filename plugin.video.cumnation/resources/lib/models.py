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


class Page(object):
    """A page of results plus a flag telling the UI whether more exist."""

    def __init__(self, items, page=1, has_next=False):
        self.items = items
        self.page = page
        self.has_next = has_next
