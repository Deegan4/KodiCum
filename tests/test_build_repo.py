# -*- coding: utf-8 -*-
"""Tests for tools/build_repo.py's Kodi-browsable directory listings."""
import os
import re
import shutil
import sys
import tempfile
import unittest
from urllib.parse import unquote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import build_repo  # noqa: E402

# Mirrors the matching rules of Kodi's CHTTPDirectory::GetDirectory: an <a href>
# only becomes a listing entry when its link text equals the unescaped href
# (ignoring a trailing slash); a trailing slash on the href marks a folder.
_ITEM = re.compile(r'<a href="([^"]*)"[^>]*>\s*(.*?)\s*</a>', re.I | re.S)


def kodi_entries(page):
    entries = []
    for href, text in _ITEM.findall(page):
        link = unquote(href.replace('&amp;', '&'))
        name = text.replace('&amp;', '&')
        if link.rstrip('/') == name.rstrip('/') and link not in ('../', '..'):
            entries.append(link)
    return entries


class IndexListingTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self._output = build_repo.OUTPUT
        build_repo.OUTPUT = self.root
        self.addCleanup(setattr, build_repo, 'OUTPUT', self._output)

        os.makedirs(os.path.join(self.root, 'repository.cumnation'))
        for name in ('addons.xml', 'addons.xml.md5',
                     os.path.join('repository.cumnation',
                                  'repository.cumnation-1.0.0.zip')):
            open(os.path.join(self.root, name), 'w').close()

    def _read(self, *parts):
        with open(os.path.join(self.root, *parts, 'index.html')) as handle:
            return handle.read()

    def test_root_lists_files_and_folders_kodi_can_parse(self):
        build_repo.write_index(self.root)
        self.assertEqual(kodi_entries(self._read()),
                         ['addons.xml', 'addons.xml.md5', 'repository.cumnation/'])

    def test_subfolder_lists_zip_and_skips_its_own_index(self):
        sub = os.path.join(self.root, 'repository.cumnation')
        build_repo.write_index(sub)
        build_repo.write_index(sub)  # rerun must not list the index itself
        self.assertEqual(kodi_entries(self._read('repository.cumnation')),
                         ['repository.cumnation-1.0.0.zip'])


class DeterministicZipTests(unittest.TestCase):
    """Rebuilding from identical sources must produce a byte-identical zip,
    or every rebuild churns repo/zips/**/*.zip in the diff for no reason."""

    def setUp(self):
        self.src = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.src)
        os.makedirs(os.path.join(self.src, 'resources'))
        with open(os.path.join(self.src, 'addon.py'), 'w') as handle:
            handle.write('print("hi")\n')
        with open(os.path.join(self.src, 'resources', 'settings.xml'), 'w') as handle:
            handle.write('<settings/>\n')
        # A stale .pyc must never make it into the zip.
        with open(os.path.join(self.src, 'addon.pyc'), 'w') as handle:
            handle.write('stale bytecode\n')

    def _build(self):
        dest = tempfile.mktemp(suffix='.zip')
        self.addCleanup(lambda: os.path.exists(dest) and os.remove(dest))
        build_repo.zip_addon('plugin.video.example', self.src, dest)
        with open(dest, 'rb') as handle:
            return handle.read()

    def test_rebuild_is_byte_identical(self):
        first = self._build()
        # Touch a file's mtime between builds; content is unchanged.
        os.utime(os.path.join(self.src, 'addon.py'), (1000000000, 1000000000))
        second = self._build()
        self.assertEqual(first, second)

    def test_excluded_extensions_are_not_packaged(self):
        import zipfile
        dest = tempfile.mktemp(suffix='.zip')
        self.addCleanup(lambda: os.path.exists(dest) and os.remove(dest))
        build_repo.zip_addon('plugin.video.example', self.src, dest)
        with zipfile.ZipFile(dest) as zf:
            names = zf.namelist()
        self.assertNotIn('plugin.video.example/addon.pyc', names)
        self.assertIn('plugin.video.example/addon.py', names)


if __name__ == '__main__':
    unittest.main()
