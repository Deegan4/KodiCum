# -*- coding: utf-8 -*-
"""Cumnation add-on entry point.

Kodi calls this module with the plugin URL as sys.argv. All routing logic
lives in resources/lib/router.py so this file stays a thin launcher.
"""
import sys

from resources.lib.router import Router


def main():
    router = Router(sys.argv)
    router.dispatch()


if __name__ == '__main__':
    main()
