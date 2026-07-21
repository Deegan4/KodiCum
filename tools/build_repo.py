#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a Kodi repository tree from the add-ons in this project.

Produces ``repo/zips/`` containing, per add-on, a versioned zip plus a merged
``addons.xml`` and its ``addons.xml.md5`` checksum — exactly what a Kodi
repository add-on's <datadir>/<info>/<checksum> URLs point at.

Run from the repo root:

    python3 tools/build_repo.py

Re-run whenever an add-on's files or version change, then commit ``repo/``.
"""
import hashlib
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


def zip_addon(addon_id, src_dir, dest_zip):
    with zipfile.ZipFile(dest_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for base, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for name in files:
                if os.path.splitext(name)[1] in EXCLUDE_EXTS:
                    continue
                abs_path = os.path.join(base, name)
                # Arcname must be prefixed with the add-on id folder.
                rel = os.path.relpath(abs_path, src_dir)
                zf.write(abs_path, os.path.join(addon_id, rel))


def build_addons_xml(addon_dirs):
    root = ET.Element('addons')
    for addon_dir in addon_dirs:
        tree = ET.parse(os.path.join(addon_dir, 'addon.xml'))
        root.append(tree.getroot())
    ET.indent(root, space='    ')
    return b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + \
        ET.tostring(root, encoding='utf-8')


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


if __name__ == '__main__':
    main()
