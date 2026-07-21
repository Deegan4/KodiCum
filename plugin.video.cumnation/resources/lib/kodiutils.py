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
