# -*- coding: utf-8 -*-
"""URL routing and directory building for the Cumnation add-on.

The router maps ``plugin://plugin.video.cumnation/?action=...`` URLs to
handler methods, builds Kodi directory listings, and drives playback.
"""
import json

try:
    from urllib.parse import urlencode, parse_qsl
except ImportError:  # pragma: no cover - Python 2 fallback
    from urllib import urlencode
    from urlparse import parse_qsl

import xbmcgui
import xbmcplugin

from . import kodiutils
from . import favorites
from . import history
from . import resume
from .content import ContentSource, ContentError
from .models import Video
from .player import ResumePlayer

S = kodiutils.get_string


class Router(object):
    def __init__(self, argv):
        self.base_url = argv[0]
        self.handle = int(argv[1])
        self.args = dict(parse_qsl(argv[2][1:]))
        self._source = None

    # -- infrastructure ---------------------------------------------------
    @property
    def source(self):
        if self._source is None:
            self._source = ContentSource()
        return self._source

    def url_for(self, **kwargs):
        return '{0}?{1}'.format(self.base_url, urlencode(kwargs))

    def dispatch(self):
        action = self.args.get('action', 'root')
        handler = getattr(self, 'action_' + action, None)
        if handler is None:
            kodiutils.log_error('Unknown action: {0}'.format(action))
            handler = self.action_root
        try:
            handler()
        except ContentError as exc:
            kodiutils.notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.endOfDirectory(self.handle, succeeded=False)

    def _end(self, content='videos', sort=True):
        xbmcplugin.setContent(self.handle, content)
        if sort:
            xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_NONE)
            xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_TITLE)
            xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_DATE)
            xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.endOfDirectory(self.handle)

    # -- directory helpers ------------------------------------------------
    def _add_dir(self, label, url, thumb=None, plot=None, context=None):
        item = xbmcgui.ListItem(label=label)
        art = {'icon': 'DefaultFolder.png'}
        if thumb:
            art.update({'thumb': thumb, 'poster': thumb, 'fanart': thumb})
        item.setArt(art)
        info = {'title': label}
        if plot:
            info['plot'] = plot
        item.setInfo('video', info)
        if context:
            item.addContextMenuItems(context)
        xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=True)

    def _add_video(self, video, context_extra=None):
        item = xbmcgui.ListItem(label=video.title)
        art = {}
        if video.thumb:
            art.update({'thumb': video.thumb, 'poster': video.thumb,
                        'icon': video.thumb, 'fanart': video.thumb})
        item.setArt(art)

        info = {'mediatype': 'video', 'title': video.title}
        if video.plot:
            info['plot'] = video.plot
        if video.duration:
            info['duration'] = int(video.duration)
        if video.date:
            info['premiered'] = video.date
        if video.rating is not None:
            try:
                info['rating'] = float(video.rating)
            except (TypeError, ValueError):
                pass
        if video.tags:
            info['tag'] = video.tags
        item.setInfo('video', info)

        item.setProperty('IsPlayable', 'true')

        # Resume badge so the user sees a partially-watched item.
        if resume.enabled():
            pos = resume.get(video.id)
            if pos:
                item.setProperty('ResumeTime', str(pos))
                if video.duration:
                    item.setProperty('TotalTime', str(video.duration))

        item.addContextMenuItems(self._video_context(video, context_extra))

        play_url = self.url_for(action='play', video_id=video.id,
                                url=video.url or '',
                                data=json.dumps(video.to_dict()))
        xbmcplugin.addDirectoryItem(self.handle, play_url, item, isFolder=False)

    def _video_context(self, video, extra=None):
        menu = []
        if favorites.is_favorite(video.id):
            menu.append((S(32031), 'RunPlugin({0})'.format(
                self.url_for(action='remove_favorite', video_id=video.id))))
        else:
            menu.append((S(32030), 'RunPlugin({0})'.format(
                self.url_for(action='add_favorite',
                             data=json.dumps(video.to_dict())))))
        if resume.enabled() and resume.get(video.id):
            menu.append((S(32032), 'RunPlugin({0})'.format(
                self.url_for(action='clear_resume', video_id=video.id))))
        if extra:
            menu.extend(extra)
        return menu

    # -- actions: navigation ---------------------------------------------
    def action_root(self):
        self._add_dir(S(32010), self.url_for(action='categories'),
                      plot=S(32011))
        self._add_dir(S(32012), self.url_for(action='search'),
                      plot=S(32013))
        self._add_dir(S(32014), self.url_for(action='favorites'),
                      plot=S(32015))
        self._add_dir(S(32016), self.url_for(action='history'),
                      plot=S(32017))
        self._add_dir(S(32018), self.url_for(action='open_settings'),
                      plot=S(32019))
        self._end(content='files', sort=False)

    def action_categories(self):
        for cat in self.source.categories():
            label = cat.name
            if cat.count:
                label = '{0} ({1})'.format(cat.name, cat.count)
            self._add_dir(label,
                          self.url_for(action='list', category=cat.id, page=1),
                          thumb=cat.thumb, plot=cat.plot)
        self._end(content='files', sort=False)

    def action_list(self):
        category = self.args.get('category', '')
        page = int(self.args.get('page', 1))
        result = self.source.list_videos(category, page)
        for video in result.items:
            self._add_video(video)
        self._add_next(result, action='list', category=category)
        self._end()

    def _add_next(self, page_result, **kwargs):
        if page_result.has_next:
            next_page = page_result.page + 1
            self._add_dir('{0} ({1})'.format(S(32020), next_page),
                          self.url_for(page=next_page, **kwargs))

    # -- actions: search --------------------------------------------------
    def action_search(self):
        self._add_dir(S(32021), self.url_for(action='new_search'))
        for term in history.search_terms():
            self._add_dir(term,
                          self.url_for(action='do_search', q=term, page=1),
                          context=[(S(32033), 'RunPlugin({0})'.format(
                              self.url_for(action='remove_search', q=term)))])
        if history.search_terms():
            self._add_dir(S(32034), self.url_for(action='clear_search'))
        self._end(content='files', sort=False)

    def action_new_search(self):
        query = kodiutils.keyboard(S(32012))
        if not query:
            self._end(content='files', sort=False)
            return
        history.add_search(query)
        self._do_search(query, 1)

    def action_do_search(self):
        query = self.args.get('q', '')
        page = int(self.args.get('page', 1))
        self._do_search(query, page)

    def _do_search(self, query, page):
        result = self.source.search(query, page)
        if not result.items and page == 1:
            kodiutils.notify(S(32022))
        for video in result.items:
            self._add_video(video)
        self._add_next(result, action='do_search', q=query)
        self._end()

    def action_remove_search(self):
        history.remove_search(self.args.get('q', ''))
        kodiutils.refresh_container()

    def action_clear_search(self):
        history.clear_search()
        kodiutils.refresh_container()

    # -- actions: favorites ----------------------------------------------
    def action_favorites(self):
        items = favorites.all_favorites()
        if not items:
            kodiutils.notify(S(32023))
        for video in items:
            self._add_video(video)
        if items:
            self._add_dir(S(32035), self.url_for(action='clear_favorites'))
        self._end()

    def action_add_favorite(self):
        video = Video.from_dict(json.loads(self.args.get('data', '{}')))
        if favorites.add(video):
            kodiutils.notify(S(32024))

    def action_remove_favorite(self):
        favorites.remove(self.args.get('video_id', ''))
        kodiutils.notify(S(32025))
        kodiutils.refresh_container()

    def action_clear_favorites(self):
        if kodiutils.yesno_dialog(S(32026)):
            favorites.clear()
            kodiutils.refresh_container()

    # -- actions: history -------------------------------------------------
    def action_history(self):
        items = history.watched()
        if not items:
            kodiutils.notify(S(32027))
        for video in items:
            self._add_video(video)
        if items:
            self._add_dir(S(32036), self.url_for(action='clear_watched'))
        self._end()

    def action_clear_watched(self):
        if kodiutils.yesno_dialog(S(32028)):
            history.clear_watched()
            kodiutils.refresh_container()

    def action_clear_resume(self):
        resume.clear(self.args.get('video_id', ''))
        kodiutils.refresh_container()

    # -- actions: playback ------------------------------------------------
    def action_play(self):
        video_id = self.args.get('video_id', '')
        video_url = self.args.get('url', '')
        video = Video.from_dict(json.loads(self.args.get('data', '{}')))

        try:
            stream, headers = self.source.resolve(video_id, video_url)
        except ContentError as exc:
            kodiutils.notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return

        if headers:
            sep = '|' + '&'.join('{0}={1}'.format(k, v) for k, v in headers.items())
            stream = stream + sep

        play_item = xbmcgui.ListItem(path=stream)
        info = {'mediatype': 'video', 'title': video.title or S(32029)}
        if video.plot:
            info['plot'] = video.plot
        play_item.setInfo('video', info)

        if resume.enabled():
            pos = resume.get(video_id)
            if pos:
                play_item.setProperty('StartOffset', str(pos))

        history.add_watched(video)
        xbmcplugin.setResolvedUrl(self.handle, True, play_item)

        # Track the resume point for next time.
        if resume.enabled() and video_id:
            ResumePlayer(video_id).run()

    def action_open_settings(self):
        kodiutils.open_settings()
