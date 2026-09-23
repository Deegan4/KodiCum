# -*- coding: utf-8 -*-
"""Tests for tools/build_static_demo.py's generated JSON tree."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import build_static_demo  # noqa: E402
import build_repo  # noqa: E402

ADDON_ROOT = os.path.join(os.path.dirname(__file__), '..', 'plugin.video.cumnation')
sys.path.insert(0, os.path.abspath(ADDON_ROOT))
from resources.lib import demo_content  # noqa: E402


class BuildStaticDemoTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        os.makedirs(os.path.join(self.root, 'zips'))  # satisfy the guard check

        self._br_output = build_repo.OUTPUT
        self._bsd_output = build_static_demo.OUTPUT
        build_repo.OUTPUT = os.path.join(self.root, 'zips')
        build_static_demo.OUTPUT = os.path.join(self.root, 'zips', 'demo-content')
        self.addCleanup(setattr, build_repo, 'OUTPUT', self._br_output)
        self.addCleanup(setattr, build_static_demo, 'OUTPUT', self._bsd_output)

        build_static_demo.main()
        self.out = build_static_demo.OUTPUT

    def _read(self, *parts):
        with open(os.path.join(self.out, *parts)) as handle:
            return json.load(handle)

    def test_refuses_to_run_before_build_repo(self):
        shutil.rmtree(os.path.join(self.root, 'zips'))
        with self.assertRaises(SystemExit):
            build_static_demo.main()

    def test_categories_match_demo_content(self):
        self.assertEqual(self._read('categories.json'),
                         {'categories': demo_content.CATEGORIES})

    def test_every_category_has_a_page_one_listing(self):
        for category_id, videos in demo_content.VIDEOS.items():
            data = self._read('list', category_id, '1.json')
            self.assertEqual(data['videos'], videos)
            self.assertFalse(data['has_next'])

    def test_every_video_has_a_resolve_file_matching_the_live_backend(self):
        for items in demo_content.VIDEOS.values():
            for video in items:
                data = self._read('resolve', '{0}.json'.format(video['id']))
                self.assertEqual(data, demo_content.resolve_payload(video['id']))

    def test_rerun_is_idempotent(self):
        before = self._read('categories.json')
        build_static_demo.main()
        self.assertEqual(self._read('categories.json'), before)


if __name__ == '__main__':
    unittest.main()
