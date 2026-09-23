# -*- coding: utf-8 -*-
"""Tests for tools/build_static_source.py: a local media folder -> a static,
serverless content source matching content.py's static-mode contract."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import build_static_source as bss  # noqa: E402


def _touch(path, content='x'):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as handle:
        handle.write(content)


class SlugHelpersTests(unittest.TestCase):
    def test_slugify_lowercases_and_dashes(self):
        self.assertEqual(bss.slugify('Home Movies!'), 'home-movies')

    def test_slugify_never_empty(self):
        self.assertEqual(bss.slugify('***'), 'x')

    def test_prettify_replaces_separators(self):
        self.assertEqual(bss.prettify('beach_trip-2020'), 'beach trip 2020')

    def test_unique_slug_dedupes(self):
        taken = set()
        self.assertEqual(bss.unique_slug('cat', taken), 'cat')
        self.assertEqual(bss.unique_slug('cat', taken), 'cat-2')
        self.assertEqual(bss.unique_slug('cat', taken), 'cat-3')


class BuildStaticSourceTests(unittest.TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media)
        self.addCleanup(shutil.rmtree, self.out)
        shutil.rmtree(self.out)  # build() must create it itself

        _touch(os.path.join(self.media, 'Featured', 'Big Buck Bunny.mp4'))
        _touch(os.path.join(self.media, 'Featured', 'Big Buck Bunny.jpg'))
        _touch(os.path.join(self.media, 'Featured', 'Big Buck Bunny.en.vtt'))
        _touch(os.path.join(self.media, 'Featured', 'Big Buck Bunny.fr.vtt'))
        _touch(os.path.join(self.media, 'Home Movies', 'beach_trip.mkv'))
        _touch(os.path.join(self.media, 'Home Movies', 'readme.txt'))  # not a video
        os.makedirs(os.path.join(self.media, 'Empty Folder'))

        self.categories, self.videos = bss.build(
            self.media, self.out, 'https://example.com/src/')  # trailing slash

    def _read(self, *parts):
        with open(os.path.join(self.out, *parts)) as handle:
            return json.load(handle)

    def test_categories_exclude_empty_folders(self):
        ids = {c['id'] for c in self.categories}
        self.assertEqual(ids, {'featured', 'home-movies'})

    def test_non_video_files_are_ignored(self):
        listing = self._read('list', 'home-movies', '1.json')
        titles = [v['title'] for v in listing['videos']]
        self.assertEqual(titles, ['beach trip'])

    def test_base_url_trailing_slash_is_not_doubled(self):
        listing = self._read('list', 'home-movies', '1.json')
        self.assertTrue(listing['videos'][0]['url'].startswith(
            'https://example.com/src/media/'))
        self.assertNotIn('src//media', listing['videos'][0]['url'])

    def test_thumb_and_subtitles_attached_to_matching_video(self):
        listing = self._read('list', 'featured', '1.json')
        video = listing['videos'][0]
        self.assertIn('thumb', video)
        self.assertTrue(video['thumb'].endswith('Big%20Buck%20Bunny.jpg'))
        langs = sorted(s['language'] for s in video['subtitles'])
        self.assertEqual(langs, ['en', 'fr'])

    def test_filenames_with_spaces_are_url_escaped(self):
        listing = self._read('list', 'featured', '1.json')
        self.assertIn('%20', listing['videos'][0]['url'])
        self.assertNotIn(' ', listing['videos'][0]['url'])

    def test_resolve_file_matches_the_list_entry(self):
        listing = self._read('list', 'featured', '1.json')
        video = listing['videos'][0]
        resolve = self._read('resolve', '{0}.json'.format(video['id']))
        self.assertEqual(resolve['stream'], video['url'])
        self.assertEqual({s['url'] for s in resolve['subtitles']},
                         {s['url'] for s in video['subtitles']})

    def test_media_files_are_copied_alongside_the_json(self):
        self.assertTrue(os.path.exists(
            os.path.join(self.out, 'media', 'featured', 'Big Buck Bunny.mp4')))
        self.assertTrue(os.path.exists(
            os.path.join(self.out, 'media', 'home-movies', 'beach_trip.mkv')))

    def test_search_index_covers_every_video_exactly_once(self):
        index = self._read('search-index.json')
        ids = [v['id'] for v in index['videos']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {v['id'] for v in self.videos})

    def test_video_ids_are_unique_across_categories(self):
        ids = [v['id'] for v in self.videos]
        self.assertEqual(len(ids), len(set(ids)))

    def test_directory_listings_are_written(self):
        self.assertTrue(os.path.exists(os.path.join(self.out, 'index.html')))
        with open(os.path.join(self.out, 'index.html')) as handle:
            self.assertIn('Index of /', handle.read())

    def test_rerun_is_idempotent(self):
        before = self._read('categories.json')
        bss.build(self.media, self.out, 'https://example.com/src/')
        self.assertEqual(self._read('categories.json'), before)


if __name__ == '__main__':
    unittest.main()
