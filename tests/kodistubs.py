# -*- coding: utf-8 -*-
"""Minimal stand-ins for the Kodi Python modules.

Kodi ships xbmc/xbmcgui/xbmcaddon/xbmcvfs/xbmcplugin as native modules that
only exist inside Kodi. To unit-test the add-on's pure logic off-device we
register just enough of them in sys.modules before importing add-on code.
"""
import os
import sys
import tempfile


class _Addon(object):
    def __init__(self, *args, **kwargs):
        # Seed the defaults declared in resources/settings.xml, matching how
        # Kodi returns a setting's default value when it has not been set.
        self._settings = {
            'page_size': '30',
            'base_url_static': 'false',
            'user_agent': 'Mozilla/5.0 (Kodi) Cumnation/1.0',
            'resume_playback': 'true',
            'track_history': 'true',
            'history_size': '50',
            'quality': '0',
            'cache_ttl': '10',
            'network_retries': '2',
            'dlna_enabled': 'true',
            'dlna_timeout': '3',
            'dlna_cache_ttl': '5',
        }
        self._profile = tempfile.mkdtemp(prefix='cumnation-test-')

    def getAddonInfo(self, key):
        return {
            'id': 'plugin.video.cumnation',
            'name': 'Cumnation',
            'path': os.getcwd(),
            'profile': self._profile,
        }.get(key, '')

    def getSetting(self, key):
        return self._settings.get(key, '')

    def setSetting(self, key, value):
        self._settings[key] = str(value)

    def getSettingBool(self, key):
        return self._settings.get(key, 'false').lower() == 'true'

    def getSettingInt(self, key):
        try:
            return int(self._settings.get(key, '0'))
        except ValueError:
            return 0

    def getLocalizedString(self, sid):
        return 'str{0}'.format(sid)

    def openSettings(self):
        pass


class _File(object):
    def __init__(self, path, mode='r'):
        self._f = open(path, mode + ('' if 'b' in mode else ''),
                       encoding=None if 'b' in mode else 'utf-8')

    def read(self):
        return self._f.read()

    def write(self, data):
        self._f.write(data)
        return True

    def close(self):
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class _InfoTag(object):
    """Stand-in for getVideoInfoTag()'s setter API (Kodi 20+)."""

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


class _ListItem(object):
    """Stand-in covering what router.py's _add_dir/_add_video/_apply_stream use."""

    def __init__(self, label='', path=None):
        self.label = label
        self.path = path
        self.art = {}
        self.info = None
        self.context_menu = []
        self.properties = {}
        self.subtitles = []
        self.mime_type = None
        self._tag = _InfoTag()

    def setArt(self, art):
        self.art = art

    def setInfo(self, kind, info):
        self.info = (kind, info)

    def getVideoInfoTag(self):
        return self._tag

    def addContextMenuItems(self, items):
        self.context_menu = list(items)

    def setProperty(self, key, value):
        self.properties[key] = value

    def setPath(self, path):
        self.path = path

    def setMimeType(self, mime_type):
        self.mime_type = mime_type

    def setContentLookup(self, value):
        pass

    def setSubtitles(self, urls):
        self.subtitles = list(urls)

    def setUniqueIDs(self, *args, **kwargs):
        pass


def install():
    xbmc = type(sys)('xbmc')
    xbmc.LOGINFO = 1
    xbmc.LOGERROR = 4
    xbmc.log = lambda *a, **k: None
    xbmc.executebuiltin = lambda *a, **k: None
    xbmc.getInfoLabel = lambda label: '20.2 (20.2.0) Git:20230000'
    xbmc.Player = object
    xbmc.Monitor = object

    xbmcaddon = type(sys)('xbmcaddon')
    xbmcaddon.Addon = _Addon

    xbmcgui = type(sys)('xbmcgui')
    xbmcgui.NOTIFICATION_INFO = 'info'
    xbmcgui.NOTIFICATION_ERROR = 'error'
    xbmcgui.ListItem = _ListItem
    xbmcgui.Dialog = object

    xbmcvfs = type(sys)('xbmcvfs')
    xbmcvfs.translatePath = lambda p: p
    xbmcvfs.exists = os.path.exists
    xbmcvfs.mkdirs = lambda p: os.makedirs(p, exist_ok=True)
    xbmcvfs.File = _File
    xbmcvfs.rename = lambda src, dst: os.rename(src, dst)

    xbmcplugin = type(sys)('xbmcplugin')
    xbmcplugin.SORT_METHOD_NONE = 0
    xbmcplugin.SORT_METHOD_TITLE = 1
    xbmcplugin.SORT_METHOD_DATE = 2
    xbmcplugin.SORT_METHOD_VIDEO_RATING = 3
    xbmcplugin.added_items = []          # tests can read/clear this list

    def _add_directory_item(handle, url, listitem, isFolder=False, totalItems=0):
        xbmcplugin.added_items.append(
            {'handle': handle, 'url': url, 'item': listitem, 'isFolder': isFolder})

    xbmcplugin.addDirectoryItem = _add_directory_item
    xbmcplugin.setContent = lambda handle, content: None
    xbmcplugin.addSortMethod = lambda handle, method: None
    xbmcplugin.endOfDirectory = lambda handle, succeeded=True, **k: None
    xbmcplugin.setResolvedUrl = lambda handle, succeeded, listitem: None

    for name, mod in [('xbmc', xbmc), ('xbmcaddon', xbmcaddon),
                      ('xbmcgui', xbmcgui), ('xbmcvfs', xbmcvfs),
                      ('xbmcplugin', xbmcplugin)]:
        sys.modules[name] = mod
