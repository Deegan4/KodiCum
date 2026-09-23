#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify an addons.xml file's contents match its addons.xml.md5 checksum.

Exits non-zero (and prints why) on a mismatch. Used by CI to verify a fresh
build, and by the Pages health check to verify what's actually being served.

    python3 tools/verify_addons_md5.py <addons.xml> <addons.xml.md5>
"""
import hashlib
import sys


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: verify_addons_md5.py <addons.xml> <addons.xml.md5>')
    xml_path, md5_path = sys.argv[1], sys.argv[2]

    with open(xml_path, 'rb') as handle:
        data = handle.read()
    with open(md5_path) as handle:
        expected = handle.read().strip()

    actual = hashlib.md5(data).hexdigest()
    if actual != expected:
        raise SystemExit('md5 mismatch: {0} hashes to {1}, but {2} says {3}'.format(
            xml_path, actual, md5_path, expected))
    print('md5 OK')


if __name__ == '__main__':
    main()
