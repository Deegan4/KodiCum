# -*- coding: utf-8 -*-
"""URL routing and directory building for the Cumnation add-on.

The router maps ``plugin://plugin.video.cumnation/?action=...`` URLs to
handler methods, builds Kodi directory listings, and drives playback.
"""
import json

try:
    from urllib.parse import urlencode, parse_qsl, quote
except ImportError:  # pragma: no cover - Python 2 fallback
    from urllib import urlencode
    from urlparse import parse_qsl
    from urllib import quote

import xbmcgui
import xbmcplugin

from . import kodiutils
from . import favorites
from . import history
from . import resume
from . import cache
from . import dlna
from . import cast
from . import trakt
from . import sources
from .content import ContentSource, ContentError
from .models import Video, Renderer, select_stream
from .player import ResumePlayer

S = kodiutils.get_string


class Router(object):
    # (sort key, label string id) in the order offered by the "Sort by" dialog.
    SORT_OPTIONS = [
        ('', 32181),
        ('title', 32182),
        ('rating', 32183),
        ('date', 32184),
        ('duration', 32185),
    ]
    # sort key -> (item -> comparable, reverse). Rating/date/duration sort
    # highest-first (best/newest/longest first feels natural when browsing);
    # title sorts A-Z.
    SORT_FUNCS = {
        'title': (lambda v: (v.title or '').lower(), False),
        'rating': (lambda v: v.rating if v.rating is not None else -1, True),
        'date': (lambda v: v.date or '', True),
        'duration': (lambda v: v.duration or 0, True),
    }

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
        except Exception as exc:
            kodiutils.log_error('Unexpected error in {0}: {1}'.format(
                self.args.get('action', '?'), exc))
            kodiutils.notify('An error occurred', icon=xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.endOfDirectory(self.handle, succeeded=False)

    def _int_arg(self, key, default=0):
        try:
            return int(self.args.get(key, default))
        except (TypeError, ValueError):
            return default

    def _end(self, content='videos', sort=True):
        xbmcplugin.setContent(self.handle, content)
        if sort:
            xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_NONE)
            xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_TITLE)
            xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_DATE)
            xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_VIDEO_RATING)
            xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)
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
        kodiutils.set_video_info(item, info)
        if context:
            item.addContextMenuItems(context)
        xbmcplugin.addDirectoryItem(self.handle, url, item, isFolder=True)

    def _add_video(self, video, context_extra=None, list_ctx=None):
        item = xbmcgui.ListItem(label=video.title)
        art = {}
        if video.thumb:
            art.update({'thumb': video.thumb, 'poster': video.thumb,
                        'icon': video.thumb})
        if video.preview:
            art['fanart'] = video.preview
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
        kodiutils.set_video_info(item, info)

        item.setProperty('IsPlayable', 'true')

        # Resume badge so the user sees a partially-watched item.
        if resume.enabled():
            pos = resume.get(video.id)
            if pos:
                item.setProperty('ResumeTime', str(pos))
                if video.duration:
                    item.setProperty('TotalTime', str(video.duration))
                    item.setProperty('Progress',
                        '{0:.0f}'.format(pos / video.duration * 100))
                    item.setProperty('ResumeLabel',
                        'Resumed at {0:.0f}%'.format(
                            pos / video.duration * 100))

        item.addContextMenuItems(self._video_context(video, context_extra))

        play_kwargs = dict(action='play', video_id=video.id,
                           url=video.url or '',
                           data=json.dumps(video.to_dict()))
        if list_ctx:
            play_kwargs.update(list_ctx)
        play_url = self.url_for(**play_kwargs)
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
        if dlna.enabled():
            menu.append((S(32070), 'RunPlugin({0})'.format(
                self.url_for(action='cast',
                             data=json.dumps(video.to_dict())))))
        if extra:
            menu.extend(extra)
        return menu

    # -- actions: navigation ---------------------------------------------
    def action_root(self):
        self._add_dir(S(32010), self.url_for(action='categories'),
                      plot=S(32011))
        self._add_dir(S(32188), self.url_for(action='continue_watching'),
                      plot=S(32189))
        self._add_dir(S(32012), self.url_for(action='search'),
                      plot=S(32013))
        self._add_dir(S(32014), self.url_for(action='favorites'),
                      plot=S(32015))
        self._add_dir(S(32016), self.url_for(action='history'),
                      plot=S(32017))
        if dlna.enabled():
            self._add_dir(S(32060), self.url_for(action='devices'),
                          plot=S(32061))
        self._add_dir(S(32018), self.url_for(action='open_settings'),
                      plot=S(32019))
        self._add_dir(S(32168), self.url_for(action='switch_source'),
                      plot=S(32169))
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
        page = self._int_arg('page', 1)
        sort_key = self.args.get('sort', '')
        result = self.source.list_videos(category, page)
        items = self._sort_items(self._filter_rating(result.items), sort_key)
        self._add_sort_dir(category, page, sort_key)
        for video in items:
            self._add_video(video, list_ctx={'category': category, 'page': page})
        self._add_next(result, action='list', category=category, sort=sort_key)
        self._end()

    def action_choose_sort(self):
        category = self.args.get('category', '')
        page = self.args.get('page', '1')
        labels = [S(sid) for _, sid in self.SORT_OPTIONS]
        choice = kodiutils.select(S(32180), labels)
        if choice < 0:
            return
        sort_key = self.SORT_OPTIONS[choice][0]
        kodiutils.navigate(self.url_for(action='list', category=category,
                                        page=page, sort=sort_key))

    def _add_next(self, page_result, **kwargs):
        if page_result.has_next:
            next_page = page_result.page + 1
            self._add_dir('{0} ({1})'.format(S(32020), next_page),
                          self.url_for(page=next_page, **kwargs))

    def _filter_rating(self, items):
        minimum = kodiutils.get_setting_int('min_rating', 0)
        if not minimum:
            return items
        return [v for v in items
                if v.rating is not None and float(v.rating) >= minimum]

    def _sort_items(self, items, sort_key):
        func = self.SORT_FUNCS.get(sort_key)
        if not func:
            return items
        key, reverse = func
        return sorted(items, key=key, reverse=reverse)

    def _add_sort_dir(self, category, page, sort_key):
        self._add_dir(S(32180),
                      self.url_for(action='choose_sort', category=category,
                                   page=page, sort=sort_key))

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
        page = self._int_arg('page', 1)
        self._do_search(query, page)

    def _do_search(self, query, page):
        result = self.source.search(query, page)
        if not result.items and page == 1:
            kodiutils.notify(S(32022))
        for video in self._filter_rating(result.items):
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

    def action_continue_watching(self):
        items = [v for v in history.watched() if resume.get(v.id) > 0]
        if not items:
            kodiutils.notify(S(32193))
        for video in items:
            self._add_video(video)
        self._end()

    def action_clear_resume(self):
        video_id = self.args.get('video_id', '')
        resume.clear(None if not video_id else video_id)
        kodiutils.refresh_container()

    # -- actions: playback ------------------------------------------------
    def _pick_stream(self, streams):
        """Apply the quality preference; prompt if set to Ask and >1 stream."""
        pref = kodiutils.get_setting_int('quality', 0)
        # Setting values: 0=Ask, 1=Best, else a resolution (e.g. 1080/720/480).
        if pref == 0 and len(streams) > 1:
            labels = [s.display_label for s in streams]
            choice = kodiutils.select(S(32041), labels)
            return streams[choice] if choice >= 0 else None
        target = 0 if pref <= 1 else pref
        return select_stream(streams, target)

    def _apply_stream(self, play_item, stream):
        """Configure a ListItem for a stream, wiring InputStream Adapter/DRM."""
        path = stream.url
        if stream.is_adaptive:
            play_item.setPath(path)
            play_item.setProperty('inputstream', 'inputstream.adapter')
            play_item.setProperty('inputstream.adapter.manifest_type',
                                  stream.manifest_type)
            if stream.headers:
                hdr = '&'.join('{0}={1}'.format(k, v)
                               for k, v in stream.headers.items())
                play_item.setProperty('inputstream.adapter.stream_headers', hdr)
            if stream.license_type:
                play_item.setProperty('inputstream.adapter.license_type',
                                      stream.license_type)
            if stream.license_key:
                play_item.setProperty('inputstream.adapter.license_key',
                                      stream.license_key)
            if stream.mime_type:
                play_item.setMimeType(stream.mime_type)
                play_item.setContentLookup(False)
        else:
            if stream.headers:
                hdr = '&'.join(
                    '{0}={1}'.format(k, quote(v))
                    for k, v in stream.headers.items())
                path = path + '|' + hdr
            play_item.setPath(path)
        if stream.subtitle:
            play_item.setSubtitles([stream.subtitle])

    def action_play(self):
        video_id = self.args.get('video_id', '')
        video_url = self.args.get('url', '')
        video = Video.from_dict(json.loads(self.args.get('data', '{}')))
        category = self.args.get('category', '')
        page = self._int_arg('page', 1)

        try:
            streams = self.source.resolve(video_id, video_url)
        except ContentError as exc:
            kodiutils.notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR)
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return

        stream = self._pick_stream(streams)
        if stream is None:                      # user cancelled the quality dialog
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return

        play_item = xbmcgui.ListItem(path=stream.url)
        self._apply_stream(play_item, stream)

        info = {'mediatype': 'video', 'title': video.title or S(32029)}
        if video.plot:
            info['plot'] = video.plot
        kodiutils.set_video_info(play_item, info)

        if resume.enabled():
            pos = resume.get(video_id)
            if pos:
                play_item.setProperty('StartOffset', str(pos))

        history.add_watched(video)
        xbmcplugin.setResolvedUrl(self.handle, True, play_item)

        # Signal Trakt that playback started.
        trakt.scrobble_start(video)

        # Block until playback stops so we can track the resume point and/or
        # queue up the next video. ResumePlayer itself only persists a resume
        # point when resume tracking is enabled; here it also runs whenever
        # auto-play-next needs to know whether the video ran to completion.
        autoplay = category and kodiutils.get_setting_bool('autoplay_next', False)
        if video_id and (resume.enabled() or autoplay):
            monitor = ResumePlayer(video_id, video)
            monitor.run()
            if autoplay and monitor.ended:
                self._maybe_autoplay_next(category, page, video_id)

    def _next_in_category(self, category, page, current_id):
        """Return (video, page) for the item after ``current_id``, or None."""
        result = self.source.list_videos(category, page)
        ids = [v.id for v in result.items]
        if current_id in ids:
            idx = ids.index(current_id)
            if idx + 1 < len(result.items):
                return result.items[idx + 1], page
        if result.has_next:
            next_page = result.page + 1
            next_result = self.source.list_videos(category, next_page)
            if next_result.items:
                return next_result.items[0], next_page
        return None

    def _maybe_autoplay_next(self, category, page, current_id):
        try:
            found = self._next_in_category(category, page, current_id)
        except ContentError:
            return
        if not found:
            return
        next_video, next_page = found
        kodiutils.notify(S(32194).format(next_video.title))
        kodiutils.play_media(self.url_for(
            action='play', video_id=next_video.id, url=next_video.url or '',
            data=json.dumps(next_video.to_dict()),
            category=category, page=next_page))

    # -- actions: maintenance / diagnostics -------------------------------
    def action_test_connection(self):
        try:
            cats = self.source.categories()
        except ContentError as exc:
            kodiutils.ok_dialog('{0}\n\n{1}'.format(S(32043), str(exc)))
            return
        kodiutils.ok_dialog(S(32044).format(len(cats)))

    def action_clear_cache(self):
        cache.clear()
        kodiutils.notify(S(32046))

    # -- actions: network devices -----------------------------------------
    def _renderers(self):
        """Return discovered renderers, scanning only when needed.

        A scan blocks for a few seconds, so warn the user before starting one
        and reuse the remembered result while it is fresh.
        """
        renderers = dlna.cached()
        if renderers is None:
            kodiutils.notify(S(32062))
            renderers = dlna.discover()
        return renderers

    def action_devices(self):
        if not dlna.enabled():
            kodiutils.notify(S(32067))
            self._end(content='files', sort=False)
            return
        renderers = self._renderers()
        if not renderers:
            kodiutils.notify(S(32063))
        for renderer in renderers:
            payload = json.dumps(renderer.to_dict())
            self._add_dir(renderer.label,
                          self.url_for(action='device_info', data=payload),
                          thumb=renderer.icon,
                          plot=renderer.description,
                          context=[(S(32072), 'RunPlugin({0})'.format(
                              self.url_for(action='device_control',
                                           data=payload)))])
        self._add_dir(S(32065), self.url_for(action='rescan_devices'))
        self._end(content='files', sort=False)

    def action_device_info(self):
        renderer = Renderer.from_dict(json.loads(self.args.get('data', '{}')))
        kodiutils.ok_dialog(renderer.description or S(32066),
                            heading=renderer.label)

    def action_rescan_devices(self):
        dlna.forget()
        kodiutils.refresh_container()

    def action_scan_devices(self):
        """Settings button: rescan now and report what turned up."""
        if not dlna.enabled():
            kodiutils.ok_dialog(S(32067))
            return
        dlna.forget()
        kodiutils.notify(S(32062))
        renderers = dlna.discover()
        if not renderers:
            kodiutils.ok_dialog(S(32063))
            return
        listing = '\n'.join(
            '{0} ({1})'.format(r.label, r.address or '?') for r in renderers)
        kodiutils.ok_dialog('{0}\n\n{1}'.format(
            S(32064).format(len(renderers)), listing))

    # -- actions: casting --------------------------------------------------
    def _choose_renderer(self):
        """Pick a device to cast to, asking only when there is a choice."""
        renderers = self._renderers()
        if not renderers:
            kodiutils.notify(S(32063))
            return None
        if len(renderers) == 1:
            return renderers[0]
        choice = kodiutils.select(S(32071), [r.label for r in renderers])
        return renderers[choice] if choice >= 0 else None

    def _pick_cast_stream(self, streams):
        """Choose a stream to hand to a TV.

        Progressive streams are strongly preferred: the device fetches the URL
        itself with no InputStream Adapter in the path, so an HLS/DASH
        manifest is only playable if the TV happens to support it natively.
        When that is all the source offers, ask rather than fail silently.
        The quality setting still applies, but "Ask" falls back to best --
        the user has already answered one dialog picking the device.
        """
        direct = [s for s in streams if not s.is_adaptive]
        if not direct:
            if not kodiutils.yesno_dialog(S(32075)):
                return None
            direct = streams
        pref = kodiutils.get_setting_int('quality', 0)
        return select_stream(direct, 0 if pref <= 1 else pref)

    def action_cast(self):
        video = Video.from_dict(json.loads(self.args.get('data', '{}')))
        renderer = self._choose_renderer()
        if renderer is None:
            return

        try:
            streams = self.source.resolve(video.id, video.url)
        except ContentError as exc:
            kodiutils.notify(str(exc), icon=xbmcgui.NOTIFICATION_ERROR)
            return

        stream = self._pick_cast_stream(streams)
        if stream is None:
            return

        try:
            cast.play(renderer, stream, video)
        except cast.CastError as exc:
            kodiutils.ok_dialog('{0}\n\n{1}'.format(S(32074), str(exc)),
                                heading=renderer.label)
            return
        history.add_watched(video)
        kodiutils.notify(S(32073).format(renderer.label))

    def action_device_control(self):
        """A small transport remote for whatever the device is playing.

        Playback lives on the TV and outlives this add-on invocation, so
        stopping or pausing it has to be an explicit action from here.
        """
        renderer = Renderer.from_dict(json.loads(self.args.get('data', '{}')))
        state = cast.transport_state(renderer)
        if state is None:
            kodiutils.ok_dialog(S(32080), heading=renderer.label)
            return

        commands = [(S(32076), cast.pause), (S(32077), cast.resume),
                    (S(32078), cast.stop)]
        heading = '{0} - {1}'.format(renderer.label, state)
        choice = kodiutils.select(heading, [label for label, _ in commands])
        if choice < 0:
            return
        try:
            commands[choice][1](renderer)
        except cast.CastError as exc:
            kodiutils.ok_dialog('{0}\n\n{1}'.format(S(32074), str(exc)),
                                heading=renderer.label)

    # -- actions: skin widgets --------------------------------------------
    def action_widget(self):
        """Flat, management-free listings for skins to bind as widgets.

        Point a skin widget at, e.g.:
            plugin://plugin.video.cumnation/?action=widget&type=favorites
            plugin://plugin.video.cumnation/?action=widget&type=history
            plugin://plugin.video.cumnation/?action=widget&type=continue
            plugin://plugin.video.cumnation/?action=widget&type=category&category=<id>
        """
        wtype = self.args.get('type', '')
        if wtype == 'favorites':
            videos = favorites.all_favorites()
        elif wtype == 'history':
            videos = history.watched()
        elif wtype == 'continue':
            videos = [v for v in history.watched() if resume.get(v.id) > 0]
        elif wtype == 'category':
            videos = self._filter_rating(
                self.source.list_videos(self.args.get('category', ''), 1).items)
        else:
            videos = []
        for video in videos:
            self._add_video(video)
        self._end()

    def action_switch_source(self):
        src_list = sources.all_sources()
        if not src_list:
            kodiutils.notify(S(32171))
            return
        labels = ['{0}'.format(s.get('name', s.get('id')))
                  for s in src_list]
        choice = kodiutils.select(S(32169), labels)
        if choice >= 0:
            sources.set_active(src_list[choice].get('id'))
            kodiutils.notify(S(32172).format(
                src_list[choice].get('name', '')))
            kodiutils.refresh_container()

    def action_open_settings(self):
        kodiutils.open_settings()
