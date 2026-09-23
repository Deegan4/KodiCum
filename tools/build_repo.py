#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a Kodi repository tree from the add-ons in this project.

Produces ``repo/zips/`` containing, per add-on, a versioned zip plus a merged
``addons.xml`` and its ``addons.xml.md5`` checksum — exactly what a Kodi
repository add-on's <datadir>/<info>/<checksum> URLs point at.

Every directory also gets an ``index.html`` listing. Kodi's File manager
"Add source" browses HTTP sources by parsing such listings; without them it
fails with "Couldn't retrieve directory information". The listings are served
by GitHub Pages (see ``.github/workflows/pages.yml``) because
raw.githubusercontent.com cannot serve directory URLs at all.

Run from the repo root:

    python3 tools/build_repo.py

Re-run whenever an add-on's files or version change, then commit ``repo/``.
"""
import hashlib
import html
import os
import shutil
import zipfile
from xml.etree import ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, 'repo', 'zips')

# Add-on folders to include in the repository.
ADDONS = ['plugin.video.cumnation', 'repository.cumnation']

# Files/dirs never shipped inside an add-on zip.
EXCLUDE_DIRS = {'__pycache__', '.git', '.github', 'tests'}
EXCLUDE_EXTS = {'.pyc', '.pyo'}


def addon_version(addon_dir):
    tree = ET.parse(os.path.join(addon_dir, 'addon.xml'))
    return tree.getroot().get('version')


# Fixed mtime baked into every zip entry so rebuilding from identical
# sources produces a byte-identical zip. Without this, every rebuild
# changes every zip (each file's real mtime gets stored), turning every
# commit's diff into repo/zips/**/*.zip noise even when nothing changed.
_FIXED_DATE_TIME = (2020, 1, 1, 0, 0, 0)


def zip_addon(addon_id, src_dir, dest_zip):
    with zipfile.ZipFile(dest_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for base, dirs, files in sorted_walk(src_dir):
            for name in sorted(files):
                if os.path.splitext(name)[1] in EXCLUDE_EXTS:
                    continue
                abs_path = os.path.join(base, name)
                # Arcname must be prefixed with the add-on id folder.
                rel = os.path.relpath(abs_path, src_dir)
                arcname = os.path.join(addon_id, rel).replace(os.sep, '/')
                info = zipfile.ZipInfo(arcname, date_time=_FIXED_DATE_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (os.stat(abs_path).st_mode & 0o777) << 16
                with open(abs_path, 'rb') as handle:
                    zf.writestr(info, handle.read())


def sorted_walk(src_dir):
    """os.walk with deterministic directory/file ordering."""
    for base, dirs, files in os.walk(src_dir):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        yield base, dirs, files


def build_addons_xml(addon_dirs):
    root = ET.Element('addons')
    for addon_dir in addon_dirs:
        tree = ET.parse(os.path.join(addon_dir, 'addon.xml'))
        root.append(tree.getroot())
    ET.indent(root, space='    ')
    return b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + \
        ET.tostring(root, encoding='utf-8')


def write_index(directory, root=None):
    """Write an Apache-style ``index.html`` listing ``directory``.

    Kodi's HTTP directory parser only accepts ``<a href>`` entries whose link
    text equals the (unescaped) href, with folders carrying a trailing slash.
    ``root`` (default: ``OUTPUT``) is only used to build the page's title;
    other tools that publish an unrelated tree (e.g. build_static_source.py)
    pass their own so the title doesn't come out relative to the wrong base.
    """
    entries = []
    for name in sorted(os.listdir(directory)):
        if name == 'index.html':
            continue
        if os.path.isdir(os.path.join(directory, name)):
            name += '/'
        entries.append('<a href="{0}">{0}</a>'.format(html.escape(name)))
    title = 'Index of /' + os.path.relpath(
        directory, root if root is not None else OUTPUT).replace(os.sep, '/')
    title = html.escape(title.rstrip('.'))
    page = ('<!DOCTYPE html>\n<html>\n<head><meta charset="utf-8">'
            '<title>{0}</title></head>\n<body>\n<h1>{0}</h1>\n<pre>\n'
            '{1}\n</pre>\n</body>\n</html>\n').format(title, '\n'.join(entries))
    with open(os.path.join(directory, 'index.html'), 'w') as handle:
        handle.write(page)


def main():
    if os.path.isdir(OUTPUT):
        shutil.rmtree(OUTPUT)
    os.makedirs(OUTPUT)

    for addon_id in ADDONS:
        src_dir = os.path.join(ROOT, addon_id)
        version = addon_version(src_dir)
        dest_dir = os.path.join(OUTPUT, addon_id)
        os.makedirs(dest_dir)
        dest_zip = os.path.join(dest_dir, '{0}-{1}.zip'.format(addon_id, version))
        zip_addon(addon_id, src_dir, dest_zip)
        print('packaged {0}-{1}.zip'.format(addon_id, version))

    addons_xml = build_addons_xml([os.path.join(ROOT, a) for a in ADDONS])
    xml_path = os.path.join(OUTPUT, 'addons.xml')
    with open(xml_path, 'wb') as handle:
        handle.write(addons_xml)

    md5 = hashlib.md5(addons_xml).hexdigest()
    with open(xml_path + '.md5', 'w') as handle:
        handle.write(md5)
    print('wrote addons.xml + addons.xml.md5 ({0})'.format(md5))

    for base, _dirs, _files in os.walk(OUTPUT):
        write_index(base)
    print('wrote index.html directory listings')


if __name__ == '__main__':
    main()
