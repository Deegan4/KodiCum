# -*- coding: utf-8 -*-
"""Thin wrappers around the Kodi Python API.

Centralising these calls keeps the rest of the code testable and makes it
obvious which bits of Kodi we depend on.
"""
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo('path'))
ADDON_PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))


def log(message, level=xbmc.LOGINFO):
    xbmc.log('[{0}] {1}'.format(ADDON_ID, message), level)


def log_error(message):
    log(message, xbmc.LOGERROR)


def get_setting(key, default=''):
    value = ADDON.getSetting(key)
    return value if value != '' else default


def get_setting_bool(key, default=False):
    try:
        return ADDON.getSettingBool(key)
    except Exception:
        value = ADDON.getSetting(key)
        return value.lower() == 'true' if value else default


def get_setting_int(key, default=0):
    try:
        return ADDON.getSettingInt(key)
    except Exception:
        value = ADDON.getSetting(key)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


def set_setting(key, value):
    ADDON.setSetting(key, str(value))


def get_string(string_id):
    return ADDON.getLocalizedString(string_id)


def notify(message, heading=None, icon=xbmcgui.NOTIFICATION_INFO, time=4000):
    xbmcgui.Dialog().notification(heading or ADDON_NAME, message, icon, time)


def ok_dialog(message, heading=None):
    return xbmcgui.Dialog().ok(heading or ADDON_NAME, message)


def yesno_dialog(message, heading=None):
    return xbmcgui.Dialog().yesno(heading or ADDON_NAME, message)


def keyboard(heading, default=''):
    """Return typed text, or None if the user cancelled."""
    result = xbmcgui.Dialog().input(heading, defaultt=default)
    return result if result else None


def select(heading, options):
    """Return the index of the chosen option, or -1 if cancelled."""
    return xbmcgui.Dialog().select(heading, options)


def open_settings():
    ADDON.openSettings()


def refresh_container():
    xbmc.executebuiltin('Container.Refresh')


def kodi_major():
    """Return Kodi's major version number (e.g. 19, 20, 21)."""
    try:
        return int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
    except (ValueError, IndexError):
        return 20


# Cache the capability check: the InfoTag setters exist from Kodi 20 (Nexus).
_USE_INFOTAG = kodi_major() >= 20


def set_video_info(list_item, info):
    """Populate a ListItem's video metadata in a version-safe way.

    Kodi 20+ deprecates ``ListItem.setInfo`` in favour of the InfoTagVideo
    setters (and will remove it in a future release). We use the modern API
    when available and fall back to ``setInfo`` on Kodi 19 (Matrix), where the
    setters do not exist.

    ``info`` uses the same keys as ``setInfo('video', ...)``: ``mediatype``,
    ``title``, ``plot``, ``duration``, ``premiered``, ``rating``, ``tag``.
    """
    if not _USE_INFOTAG:
        list_item.setInfo('video', info)
        return

    tag = list_item.getVideoInfoTag()
    if 'mediatype' in info:
        tag.setMediaType(info['mediatype'])
    if 'title' in info:
        tag.setTitle(info['title'])
    if 'plot' in info:
        tag.setPlot(info['plot'])
    if info.get('duration') is not None:
        tag.setDuration(int(info['duration']))
    if info.get('premiered'):
        tag.setPremiered(info['premiered'])
    if info.get('rating') is not None:
        tag.setRating(float(info['rating']))
    if info.get('tag'):
        tag.setTags(list(info['tag']))
