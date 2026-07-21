# -*- coding: utf-8 -*-
"""Off-device unit tests for the add-on's pure logic.

Run from the repo root:

    python3 -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import kodistubs
kodistubs.install()

# Make the add-on package importable as 'resources.lib.*'.
ADDON_ROOT = os.path.join(os.path.dirname(__file__), '..', 'plugin.video.cumnation')
sys.path.insert(0, os.path.abspath(ADDON_ROOT))

from resources.lib import favorites, history, resume, kodiutils  # noqa: E402
from resources.lib.models import Video, Category, Page  # noqa: E402


class _FakeInfoTag(object):
    def __init__(self):
        self.calls = {}

    def setMediaType(self, v):
        self.calls['mediatype'] = v

    def setTitle(self, v):
        self.calls['title'] = v

    def setPlot(self, v):
        self.calls['plot'] = v

    def setDuration(self, v):
        self.calls['duration'] = v

    def setPremiered(self, v):
        self.calls['premiered'] = v

    def setRating(self, v):
        self.calls['rating'] = v

    def setTags(self, v):
        self.calls['tag'] = v


class _FakeListItem(object):
    def __init__(self):
        self.info = None
        self.tag = _FakeInfoTag()

    def setInfo(self, kind, info):
        self.info = (kind, info)

    def getVideoInfoTag(self):
        return self.tag


def make_video(vid='v1', title='Test'):
    return Video(vid=vid, title=title, url='http://x/v.mp4', duration=600)


class ModelTests(unittest.TestCase):
    def test_video_roundtrip(self):
        v = make_video()
        self.assertEqual(Video.from_dict(v.to_dict()).title, v.title)

    def test_category_roundtrip(self):
        c = Category(cid='c1', name='Cat', count=5)
        self.assertEqual(Category.from_dict(c.to_dict()).count, 5)

    def test_page_defaults(self):
        p = Page([make_video()])
        self.assertEqual(p.page, 1)
        self.assertFalse(p.has_next)


class FavoritesTests(unittest.TestCase):
    def setUp(self):
        favorites.clear()

    def test_add_and_detect(self):
        self.assertTrue(favorites.add(make_video('a')))
        self.assertTrue(favorites.is_favorite('a'))

    def test_no_duplicates(self):
        favorites.add(make_video('a'))
        self.assertFalse(favorites.add(make_video('a')))
        self.assertEqual(len(favorites.all_favorites()), 1)

    def test_toggle(self):
        v = make_video('t')
        self.assertTrue(favorites.toggle(v))   # added
        self.assertFalse(favorites.toggle(v))  # removed
        self.assertFalse(favorites.is_favorite('t'))


class SearchHistoryTests(unittest.TestCase):
    def setUp(self):
        history.clear_search()

    def test_recent_first_and_dedup(self):
        history.add_search('alpha')
        history.add_search('beta')
        history.add_search('alpha')
        self.assertEqual(history.search_terms(), ['alpha', 'beta'])

    def test_remove(self):
        history.add_search('gamma')
        history.remove_search('gamma')
        self.assertEqual(history.search_terms(), [])


class ResumeTests(unittest.TestCase):
    def setUp(self):
        resume.clear()

    def test_saves_meaningful_position(self):
        resume.set('v1', 120, 600)
        self.assertAlmostEqual(resume.get('v1'), 120, delta=0.1)

    def test_ignores_tiny_position(self):
        resume.set('v2', 3, 600)
        self.assertEqual(resume.get('v2'), 0.0)

    def test_clears_when_finished(self):
        resume.set('v3', 120, 600)
        resume.set('v3', 590, 600)  # >95% watched
        self.assertEqual(resume.get('v3'), 0.0)


class VideoInfoCompatTests(unittest.TestCase):
    """The version-safe metadata helper must pick the right Kodi API."""

    INFO = {'mediatype': 'video', 'title': 'T', 'plot': 'P',
            'duration': 60, 'premiered': '01.01.2020', 'rating': 7.5,
            'tag': ['a', 'b']}

    def test_kodi_major_parsing(self):
        # Stub reports 20.2 -> major 20.
        self.assertEqual(kodiutils.kodi_major(), 20)

    def test_uses_infotag_on_kodi_20_plus(self):
        original = kodiutils._USE_INFOTAG
        kodiutils._USE_INFOTAG = True
        try:
            item = _FakeListItem()
            kodiutils.set_video_info(item, self.INFO)
            self.assertIsNone(item.info)  # setInfo NOT used
            self.assertEqual(item.tag.calls['title'], 'T')
            self.assertEqual(item.tag.calls['duration'], 60)
            self.assertEqual(item.tag.calls['tag'], ['a', 'b'])
        finally:
            kodiutils._USE_INFOTAG = original

    def test_falls_back_to_setinfo_on_kodi_19(self):
        original = kodiutils._USE_INFOTAG
        kodiutils._USE_INFOTAG = False
        try:
            item = _FakeListItem()
            kodiutils.set_video_info(item, self.INFO)
            self.assertEqual(item.info[0], 'video')      # setInfo used
            self.assertEqual(item.info[1]['title'], 'T')
            self.assertEqual(item.tag.calls, {})         # InfoTag NOT touched
        finally:
            kodiutils._USE_INFOTAG = original


if __name__ == '__main__':
    unittest.main()
