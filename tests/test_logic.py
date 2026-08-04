# -*- coding: utf-8 -*-
"""Off-device unit tests for the add-on's pure logic.

Run from the repo root:

    python3 -m unittest discover -s tests
"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import kodistubs
kodistubs.install()

# Make the add-on package importable as 'resources.lib.*'.
ADDON_ROOT = os.path.join(os.path.dirname(__file__), '..', 'plugin.video.cumnation')
sys.path.insert(0, os.path.abspath(ADDON_ROOT))

from resources.lib import favorites, history, resume, kodiutils, cache, dlna  # noqa: E402
from resources.lib.models import (  # noqa: E402
    Video, Category, Page, Stream, Renderer, select_stream)


class _FakeInfoTag(object):
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


class _FakeListItem(object):
    def __init__(self):
        self.info = None
        self.tag = _FakeInfoTag()

    def setInfo(self, kind, info):
        self.info = (kind, info)

    def getVideoInfoTag(self):
        return self.tag


def make_video(vid='v1', title='Test'):
    return Video(vid=vid, title=title, url='http://x/v.mp4', duration=600)


class ModelTests(unittest.TestCase):
    def test_video_roundtrip(self):
        v = make_video()
        self.assertEqual(Video.from_dict(v.to_dict()).title, v.title)

    def test_category_roundtrip(self):
        c = Category(cid='c1', name='Cat', count=5)
        self.assertEqual(Category.from_dict(c.to_dict()).count, 5)

    def test_page_defaults(self):
        p = Page([make_video()])
        self.assertEqual(p.page, 1)
        self.assertFalse(p.has_next)


class FavoritesTests(unittest.TestCase):
    def setUp(self):
        favorites.clear()

    def test_add_and_detect(self):
        self.assertTrue(favorites.add(make_video('a')))
        self.assertTrue(favorites.is_favorite('a'))

    def test_no_duplicates(self):
        favorites.add(make_video('a'))
        self.assertFalse(favorites.add(make_video('a')))
        self.assertEqual(len(favorites.all_favorites()), 1)

    def test_toggle(self):
        v = make_video('t')
        self.assertTrue(favorites.toggle(v))   # added
        self.assertFalse(favorites.toggle(v))  # removed
        self.assertFalse(favorites.is_favorite('t'))


class SearchHistoryTests(unittest.TestCase):
    def setUp(self):
        history.clear_search()

    def test_recent_first_and_dedup(self):
        history.add_search('alpha')
        history.add_search('beta')
        history.add_search('alpha')
        self.assertEqual(history.search_terms(), ['alpha', 'beta'])

    def test_remove(self):
        history.add_search('gamma')
        history.remove_search('gamma')
        self.assertEqual(history.search_terms(), [])


class ResumeTests(unittest.TestCase):
    def setUp(self):
        resume.clear()

    def test_saves_meaningful_position(self):
        resume.set('v1', 120, 600)
        self.assertAlmostEqual(resume.get('v1'), 120, delta=0.1)

    def test_ignores_tiny_position(self):
        resume.set('v2', 3, 600)
        self.assertEqual(resume.get('v2'), 0.0)

    def test_clears_when_finished(self):
        resume.set('v3', 120, 600)
        resume.set('v3', 590, 600)  # >95% watched
        self.assertEqual(resume.get('v3'), 0.0)


class VideoInfoCompatTests(unittest.TestCase):
    """The version-safe metadata helper must pick the right Kodi API."""

    INFO = {'mediatype': 'video', 'title': 'T', 'plot': 'P',
            'duration': 60, 'premiered': '01.01.2020', 'rating': 7.5,
            'tag': ['a', 'b']}

    def test_kodi_major_parsing(self):
        # Stub reports 20.2 -> major 20.
        self.assertEqual(kodiutils.kodi_major(), 20)

    def test_uses_infotag_on_kodi_20_plus(self):
        original = kodiutils._USE_INFOTAG
        kodiutils._USE_INFOTAG = True
        try:
            item = _FakeListItem()
            kodiutils.set_video_info(item, self.INFO)
            self.assertIsNone(item.info)  # setInfo NOT used
            self.assertEqual(item.tag.calls['title'], 'T')
            self.assertEqual(item.tag.calls['duration'], 60)
            self.assertEqual(item.tag.calls['tag'], ['a', 'b'])
        finally:
            kodiutils._USE_INFOTAG = original

    def test_falls_back_to_setinfo_on_kodi_19(self):
        original = kodiutils._USE_INFOTAG
        kodiutils._USE_INFOTAG = False
        try:
            item = _FakeListItem()
            kodiutils.set_video_info(item, self.INFO)
            self.assertEqual(item.info[0], 'video')      # setInfo used
            self.assertEqual(item.info[1]['title'], 'T')
            self.assertEqual(item.tag.calls, {})         # InfoTag NOT touched
        finally:
            kodiutils._USE_INFOTAG = original


class StreamTests(unittest.TestCase):
    def test_from_dict_accepts_url_or_stream_key(self):
        self.assertEqual(Stream.from_dict({'url': 'a'}).url, 'a')
        self.assertEqual(Stream.from_dict({'stream': 'b'}).url, 'b')

    def test_adaptive_flag_and_label(self):
        s = Stream(url='u', manifest_type='hls', quality=720)
        self.assertTrue(s.is_adaptive)
        self.assertEqual(s.display_label, '720p')
        self.assertEqual(Stream(url='u').display_label, 'Default')


class SelectStreamTests(unittest.TestCase):
    def _streams(self):
        return [Stream('a', quality=1080), Stream('b', quality=720),
                Stream('c', quality=480)]

    def test_single_stream_returned_directly(self):
        one = [Stream('x', quality=480)]
        self.assertIs(select_stream(one, 1080), one[0])

    def test_zero_preference_picks_highest(self):
        self.assertEqual(select_stream(self._streams(), 0).quality, 1080)

    def test_target_picks_at_or_below(self):
        self.assertEqual(select_stream(self._streams(), 720).quality, 720)
        self.assertEqual(select_stream(self._streams(), 600).quality, 480)

    def test_target_below_all_falls_back_to_highest(self):
        self.assertEqual(select_stream(self._streams(), 240).quality, 1080)


class CacheTests(unittest.TestCase):
    def setUp(self):
        cache.clear()
        kodiutils.set_setting('cache_ttl', '10')   # 10 min

    def test_hit_within_ttl(self):
        cache.set('k', {'v': 1}, now=1000)
        self.assertEqual(cache.get('k', now=1200), {'v': 1})

    def test_miss_after_ttl(self):
        cache.set('k', {'v': 1}, now=1000)
        self.assertIsNone(cache.get('k', now=1000 + 601))

    def test_disabled_when_ttl_zero(self):
        cache.set('k', {'v': 1}, now=1000)
        kodiutils.set_setting('cache_ttl', '0')
        self.assertIsNone(cache.get('k', now=1000))


NS = 'urn:schemas-upnp-org:device-1-0'

RENDERER_XML = """<?xml version="1.0"?>
<root xmlns="{ns}">
  <device>
    <deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>
    <friendlyName>Living Room TV</friendlyName>
    <manufacturer>Samsung Electronics</manufacturer>
    <modelName>UN55TU8000</modelName>
    <modelNumber>TU8000</modelNumber>
    <UDN>uuid:aaaa-1111</UDN>
    <iconList>
      <icon><width>48</width><url>/icon48.png</url></icon>
      <icon><width>120</width><url>/icon120.png</url></icon>
    </iconList>
    <serviceList>
      <service>
        <serviceType>urn:schemas-upnp-org:service:RenderingControl:1</serviceType>
        <controlURL>/rc/control</controlURL>
      </service>
      <service>
        <serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>
        <controlURL>/avt/control</controlURL>
      </service>
    </serviceList>
  </device>
</root>""".format(ns=NS)

# A vendor root device with the renderer nested inside deviceList.
NESTED_XML = """<?xml version="1.0"?>
<root xmlns="{ns}">
  <URLBase>http://10.0.0.9:2870/</URLBase>
  <device>
    <deviceType>urn:vendor:device:Box:1</deviceType>
    <friendlyName>Vendor Box</friendlyName>
    <UDN>uuid:outer</UDN>
    <deviceList>
      <device>
        <deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType>
        <friendlyName>Bedroom TV</friendlyName>
        <UDN>uuid:bbbb-2222</UDN>
        <serviceList>
          <service>
            <serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>
            <controlURL>avt/ctrl</controlURL>
          </service>
        </serviceList>
      </device>
    </deviceList>
  </device>
</root>""".format(ns=NS)

# A NAS media *server* -- discoverable, but nothing can be played to it.
SERVER_XML = """<?xml version="1.0"?>
<root xmlns="{ns}">
  <device>
    <deviceType>urn:schemas-upnp-org:device:MediaServer:1</deviceType>
    <friendlyName>Basement NAS</friendlyName>
    <UDN>uuid:cccc-3333</UDN>
    <serviceList>
      <service>
        <serviceType>urn:schemas-upnp-org:service:ContentDirectory:1</serviceType>
        <controlURL>/cd/control</controlURL>
      </service>
    </serviceList>
  </device>
</root>""".format(ns=NS)

SSDP_RESPONSE = (
    'HTTP/1.1 200 OK\r\n'
    'CACHE-CONTROL: max-age=1800\r\n'
    'LOCATION: http://192.168.1.50:9197/dmr\r\n'
    'ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n'
    'USN: uuid:aaaa-1111::urn:schemas-upnp-org:device:MediaRenderer:1\r\n'
    'SERVER: Linux/4.1 UPnP/1.0 Samsung/1.0\r\n'
    '\r\n'
)


class SsdpParseTests(unittest.TestCase):
    def test_headers_lowercased_and_status_line_dropped(self):
        headers = dlna.parse_ssdp_response(SSDP_RESPONSE)
        self.assertEqual(headers['location'], 'http://192.168.1.50:9197/dmr')
        self.assertIn('usn', headers)
        self.assertNotIn('http/1.1 200 ok', headers)

    def test_tolerates_junk_lines(self):
        headers = dlna.parse_ssdp_response(
            'HTTP/1.1 200 OK\r\ngarbage\r\n\r\nLOCATION: http://x/d.xml\r\n')
        self.assertEqual(headers, {'location': 'http://x/d.xml'})

    def test_first_duplicate_header_wins(self):
        headers = dlna.parse_ssdp_response(
            'HTTP/1.1 200 OK\r\nST: a\r\nST: b\r\n')
        self.assertEqual(headers['st'], 'a')

    def test_msearch_payload_is_wellformed(self):
        payload = dlna._msearch('urn:test', 3).decode('utf-8')
        self.assertTrue(payload.startswith('M-SEARCH * HTTP/1.1\r\n'))
        self.assertIn('MAN: "ssdp:discover"\r\n', payload)
        self.assertIn('ST: urn:test\r\n', payload)
        self.assertTrue(payload.endswith('\r\n\r\n'))


class DeviceDescriptionTests(unittest.TestCase):
    LOCATION = 'http://192.168.1.50:9197/dmr/desc.xml'

    def test_parses_renderer_fields(self):
        r = dlna.parse_device_description(RENDERER_XML, self.LOCATION)
        self.assertEqual(r.name, 'Living Room TV')
        self.assertEqual(r.udn, 'uuid:aaaa-1111')
        self.assertEqual(r.manufacturer, 'Samsung Electronics')
        self.assertEqual(r.model, 'UN55TU8000')
        self.assertEqual(r.address, '192.168.1.50')

    def test_control_url_resolved_against_location(self):
        r = dlna.parse_device_description(RENDERER_XML, self.LOCATION)
        self.assertEqual(r.control_url,
                         'http://192.168.1.50:9197/avt/control')

    def test_picks_largest_icon(self):
        r = dlna.parse_device_description(RENDERER_XML, self.LOCATION)
        self.assertEqual(r.icon, 'http://192.168.1.50:9197/icon120.png')

    def test_finds_embedded_renderer_and_honours_urlbase(self):
        r = dlna.parse_device_description(NESTED_XML, 'http://10.0.0.9:80/d.xml')
        self.assertEqual(r.name, 'Bedroom TV')
        self.assertEqual(r.control_url, 'http://10.0.0.9:2870/avt/ctrl')

    def test_rejects_device_without_avtransport(self):
        self.assertIsNone(
            dlna.parse_device_description(SERVER_XML, self.LOCATION))

    def test_rejects_unparseable_xml(self):
        self.assertIsNone(
            dlna.parse_device_description('<not xml', self.LOCATION))

    def test_address_from_ssdp_overrides_location_host(self):
        r = dlna.parse_device_description(RENDERER_XML, self.LOCATION,
                                          address='192.168.1.51')
        self.assertEqual(r.address, '192.168.1.51')


class RendererAssemblyTests(unittest.TestCase):
    def _fetch(self, mapping):
        return lambda location: mapping.get(location)

    def test_filters_non_renderers_and_sorts_by_name(self):
        responses = [
            {'location': 'http://a/d.xml', 'address': '10.0.0.1'},
            {'location': 'http://b/d.xml', 'address': '10.0.0.2'},
            {'location': 'http://c/d.xml', 'address': '10.0.0.3'},
        ]
        found = dlna.renderers_from_responses(responses, self._fetch({
            'http://a/d.xml': RENDERER_XML,     # Living Room TV
            'http://b/d.xml': SERVER_XML,       # dropped: no AVTransport
            'http://c/d.xml': NESTED_XML,       # Bedroom TV
        }))
        self.assertEqual([r.name for r in found],
                         ['Bedroom TV', 'Living Room TV'])

    def test_deduplicates_by_udn(self):
        # The same TV answering both search targets from two URLs.
        responses = [{'location': 'http://a/d.xml'},
                     {'location': 'http://a2/d.xml'}]
        found = dlna.renderers_from_responses(responses, self._fetch({
            'http://a/d.xml': RENDERER_XML,
            'http://a2/d.xml': RENDERER_XML,
        }))
        self.assertEqual(len(found), 1)

    def test_unreachable_description_is_skipped(self):
        responses = [{'location': 'http://down/d.xml'}]
        self.assertEqual(
            dlna.renderers_from_responses(responses, lambda loc: None), [])

    def test_response_without_location_is_skipped(self):
        self.assertEqual(
            dlna.renderers_from_responses([{'st': 'x'}], lambda loc: None), [])


class RendererModelTests(unittest.TestCase):
    def test_roundtrip(self):
        r = dlna.parse_device_description(RENDERER_XML, 'http://h:80/d.xml')
        self.assertEqual(Renderer.from_dict(r.to_dict()).control_url,
                         r.control_url)

    def test_label_falls_back_to_address(self):
        self.assertEqual(Renderer(udn='u', name='', address='10.0.0.4').label,
                         '10.0.0.4')

    def test_description_lines(self):
        r = Renderer(udn='u', name='TV', manufacturer='LG', model='OLED55',
                     model_number='C1', address='10.0.0.5')
        self.assertEqual(r.description, 'LG OLED55\nC1\n10.0.0.5')

    def test_description_empty_when_nothing_reported(self):
        self.assertEqual(Renderer(udn='u', name='TV').description, '')


class DeviceCacheTests(unittest.TestCase):
    def setUp(self):
        dlna.forget()
        kodiutils.set_setting('dlna_cache_ttl', '5')   # 5 min

    def _one(self):
        return [dlna.parse_device_description(RENDERER_XML, 'http://h/d.xml')]

    def test_miss_when_never_scanned(self):
        self.assertIsNone(dlna.cached())

    def test_hit_within_ttl(self):
        dlna._remember(self._one())
        cached = dlna.cached()
        self.assertEqual([r.name for r in cached], ['Living Room TV'])

    def test_miss_after_ttl(self):
        dlna._remember(self._one())
        self.assertIsNone(dlna.cached(now=time.time() + 301))

    def test_empty_scan_result_still_caches(self):
        # An empty list is a real answer ("nothing on this network"), not a
        # miss -- otherwise every visit would rescan for several seconds.
        dlna._remember([])
        self.assertEqual(dlna.cached(), [])

    def test_disabled_when_ttl_zero(self):
        dlna._remember(self._one())
        kodiutils.set_setting('dlna_cache_ttl', '0')
        self.assertIsNone(dlna.cached())

    def test_forget_drops_result(self):
        dlna._remember(self._one())
        dlna.forget()
        self.assertIsNone(dlna.cached())


class DeviceSettingsTests(unittest.TestCase):
    def test_defaults(self):
        self.assertTrue(dlna.enabled())
        self.assertEqual(dlna.timeout(), 3)
        self.assertEqual(dlna.cache_ttl(), 300)

    def test_timeout_floor(self):
        kodiutils.set_setting('dlna_timeout', '0')
        try:
            self.assertEqual(dlna.timeout(), 1)
        finally:
            kodiutils.set_setting('dlna_timeout', '3')


if __name__ == '__main__':
    unittest.main()
