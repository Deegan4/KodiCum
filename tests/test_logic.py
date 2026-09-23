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

# content.py imports the `requests` package, which CI intentionally never
# pip-installs (the off-device suite has no dependencies of its own; a real
# Kodi install provides it via script.module.requests). Stub it so importing
# content here at module level, and instantiating ContentSource() in tests,
# doesn't require it to actually be present.
if 'requests' not in sys.modules:
    _requests_stub = type(sys)('requests')

    class _StubSession(object):
        def __init__(self):
            self.headers = {}

        def get(self, *args, **kwargs):
            raise NotImplementedError('network access is not available in tests')

    class _StubRequestException(Exception):
        pass

    _requests_stub.Session = _StubSession
    _requests_stub.RequestException = _StubRequestException
    sys.modules['requests'] = _requests_stub

from resources.lib import (  # noqa: E402
    favorites, history, resume, kodiutils, cache, dlna, cast,
    sources, trakt, content)
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


def make_video(vid='v1', title='Test', preview=None):
    return Video(vid=vid, title=title, url='http://x/v.mp4', duration=600,
                 preview=preview)


class ModelTests(unittest.TestCase):
    def test_video_roundtrip(self):
        v = make_video()
        self.assertEqual(Video.from_dict(v.to_dict()).title, v.title)

    def test_video_preview_roundtrip(self):
        v = make_video(preview='http://h/preview.jpg')
        d = v.to_dict()
        self.assertEqual(d['preview'], 'http://h/preview.jpg')
        self.assertEqual(Video.from_dict(d).preview, 'http://h/preview.jpg')

    def test_video_preview_omitted_when_none(self):
        v = make_video()
        self.assertNotIn('preview', v.to_dict())

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

    def test_clear_none_clears_all(self):
        resume.set('v1', 120, 600)
        resume.set('v2', 60, 600)
        resume.clear(None)
        self.assertEqual(resume.get('v1'), 0.0)
        self.assertEqual(resume.get('v2'), 0.0)

    def test_clear_empty_string_does_not_clear_all(self):
        resume.set('v1', 120, 600)
        resume.clear('')
        self.assertAlmostEqual(resume.get('v1'), 120, delta=0.1)

    def test_clear_specific_video(self):
        resume.set('v1', 120, 600)
        resume.set('v2', 60, 600)
        resume.clear('v1')
        self.assertEqual(resume.get('v1'), 0.0)
        self.assertAlmostEqual(resume.get('v2'), 60, delta=0.1)


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

    def test_max_entries_evicts_oldest(self):
        cache.clear()
        kodiutils.set_setting('cache_ttl', '60')
        original = cache.MAX_ENTRIES
        cache.MAX_ENTRIES = 3
        try:
            for i in range(5):
                cache.set('key{0}'.format(i), i, now=1000 + i)
            self.assertIsNotNone(cache.get('key4', now=1005))
            self.assertIsNone(cache.get('key0', now=1005))
        finally:
            cache.MAX_ENTRIES = original


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


FAULT_XML = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body><s:Fault>
    <faultcode>s:Client</faultcode>
    <detail>
      <UPnPError xmlns="urn:schemas-upnp-org:control-1-0">
        <errorCode>714</errorCode>
        <errorDescription>Illegal MIME-type</errorDescription>
      </UPnPError>
    </detail>
  </s:Fault></s:Body>
</s:Envelope>"""

TRANSPORT_INFO_XML = """<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <u:GetTransportInfoResponse
        xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
      <CurrentTransportState>PLAYING</CurrentTransportState>
      <CurrentSpeed>1</CurrentSpeed>
    </u:GetTransportInfoResponse>
  </s:Body>
</s:Envelope>"""


def make_renderer():
    return Renderer(udn='uuid:tv', name='Living Room TV',
                    address='192.168.1.50',
                    control_url='http://192.168.1.50:9197/upnp/control/AVT',
                    service_type='urn:schemas-upnp-org:service:AVTransport:2')


class CastableUrlTests(unittest.TestCase):
    def test_accepts_http_urls(self):
        self.assertTrue(cast.is_castable('http://host/v.mp4'))
        self.assertTrue(cast.is_castable('https://host/v.mp4'))

    def test_rejects_urls_the_tv_could_not_fetch(self):
        # The device downloads the URL itself, so anything Kodi resolves
        # internally is useless to it.
        for url in ('plugin://plugin.video.cumnation/?action=play',
                    'file:///home/user/v.mp4', '/home/user/v.mp4', '', None):
            self.assertFalse(cast.is_castable(url), url)


class MimeAndDurationTests(unittest.TestCase):
    def test_guesses_from_extension(self):
        self.assertEqual(cast.guess_mime('http://h/a/v.mkv'),
                         'video/x-matroska')
        self.assertEqual(cast.guess_mime('http://h/v.M3U8'),
                         'application/vnd.apple.mpegurl')

    def test_query_string_does_not_confuse_extension(self):
        self.assertEqual(cast.guess_mime('http://h/v.mp4?token=a.mkv'),
                         'video/mp4')

    def test_unknown_extension_falls_back(self):
        self.assertEqual(cast.guess_mime('http://h/stream'), 'video/mp4')

    def test_duration_formatting(self):
        self.assertEqual(cast.format_duration(3661), '1:01:01.000')
        self.assertEqual(cast.format_duration(600), '0:10:00.000')

    def test_duration_rejects_unusable_values(self):
        for value in (0, -5, None, 'abc'):
            self.assertIsNone(cast.format_duration(value))


class MetadataTests(unittest.TestCase):
    def test_includes_title_artwork_and_duration(self):
        video = Video(vid='v1', title='My Movie', plot='A plot',
                      thumb='http://h/t.jpg', duration=600)
        didl = cast.build_metadata(Stream('http://h/v.mp4'), video)
        self.assertIn('<dc:title>My Movie</dc:title>', didl)
        self.assertIn('<upnp:class>object.item.videoItem</upnp:class>', didl)
        self.assertIn('http://h/t.jpg', didl)
        self.assertIn('duration="0:10:00.000"', didl)

    def test_declares_protocol_info_with_dlna_flags(self):
        didl = cast.build_metadata(Stream('http://h/v.mkv'))
        self.assertIn('http-get:*:video/x-matroska:DLNA.ORG_OP=01', didl)

    def test_explicit_stream_mime_wins_over_extension(self):
        stream = Stream('http://h/stream', mime_type='video/webm')
        self.assertIn('http-get:*:video/webm:', cast.build_metadata(stream))

    def test_escapes_xml_in_titles_and_urls(self):
        video = Video(vid='v1', title='Tom & Jerry <2>')
        didl = cast.build_metadata(
            Stream('http://h/v.mp4?a=1&b=2'), video)
        self.assertIn('Tom &amp; Jerry &lt;2&gt;', didl)
        self.assertIn('a=1&amp;b=2', didl)
        # Must still be well-formed XML after escaping.
        __import__('xml.etree.ElementTree', fromlist=['x']).fromstring(didl)

    def test_survives_missing_video_metadata(self):
        didl = cast.build_metadata(Stream('http://h/v.mp4'))
        self.assertIn('<dc:title>Video</dc:title>', didl)
        self.assertNotIn('duration=', didl)


class SoapEnvelopeTests(unittest.TestCase):
    def test_preserves_argument_order(self):
        # UPnP actions are positional; a reordered body is rejected.
        envelope = cast.build_envelope(
            'urn:schemas-upnp-org:service:AVTransport:1', 'SetAVTransportURI',
            (('InstanceID', 0), ('CurrentURI', 'http://h/v.mp4'),
             ('CurrentURIMetaData', '')))
        self.assertLess(envelope.index('<InstanceID>'),
                        envelope.index('<CurrentURI>'))
        self.assertLess(envelope.index('<CurrentURI>'),
                        envelope.index('<CurrentURIMetaData>'))

    def test_escapes_argument_values(self):
        envelope = cast.build_envelope('urn:x', 'Play',
                                       (('Meta', '<DIDL-Lite a="1"/>'),))
        self.assertIn('&lt;DIDL-Lite', envelope)
        __import__('xml.etree.ElementTree', fromlist=['x']).fromstring(envelope)

    def test_names_the_action_and_service(self):
        envelope = cast.build_envelope('urn:svc:2', 'Stop',
                                       (('InstanceID', 0),))
        self.assertIn('<u:Stop xmlns:u="urn:svc:2">', envelope)
        self.assertIn('</u:Stop>', envelope)


class SoapResponseTests(unittest.TestCase):
    def test_parses_response_values(self):
        values = cast.parse_response(TRANSPORT_INFO_XML)
        self.assertEqual(values['CurrentTransportState'], 'PLAYING')
        self.assertEqual(values['CurrentSpeed'], '1')

    def test_parses_upnp_fault_code_and_description(self):
        self.assertEqual(cast.parse_fault(FAULT_XML),
                         'Illegal MIME-type (714)')

    def test_unparseable_bodies_degrade(self):
        self.assertEqual(cast.parse_response('<not xml'), {})
        self.assertIsNone(cast.parse_fault('<not xml'))
        self.assertIsNone(cast.parse_fault('<a><b/></a>'))


class CastCommandTests(unittest.TestCase):
    """Exercise the command layer with the single network call replaced."""

    def setUp(self):
        self.calls = []
        self.original = cast.soap_request
        self.responses = {}

        def recorder(renderer, action, arguments=()):
            self.calls.append((action, list(arguments)))
            if action in self.failing:
                raise cast.CastError('boom')
            return self.responses.get(action, {})

        self.failing = set()
        cast.soap_request = recorder

    def tearDown(self):
        cast.soap_request = self.original

    def _actions(self):
        return [action for action, _ in self.calls]

    def test_play_stops_then_sets_uri_then_plays(self):
        cast.play(make_renderer(), Stream('http://h/v.mp4'), make_video())
        self.assertEqual(self._actions(),
                         ['Stop', 'SetAVTransportURI', 'Play'])

    def test_play_sends_url_and_metadata_in_order(self):
        cast.play(make_renderer(), Stream('http://h/v.mp4'), make_video())
        args = dict(self.calls[1][1])
        self.assertEqual(args['CurrentURI'], 'http://h/v.mp4')
        self.assertIn('<dc:title>Test</dc:title>', args['CurrentURIMetaData'])
        self.assertEqual(self.calls[2][1], [('InstanceID', 0), ('Speed', 1)])

    def test_preparatory_stop_failure_is_ignored(self):
        # An idle renderer may reject Stop; that must not abort the cast.
        self.failing = {'Stop'}
        cast.play(make_renderer(), Stream('http://h/v.mp4'))
        self.assertEqual(self._actions(),
                         ['Stop', 'SetAVTransportURI', 'Play'])

    def test_set_uri_failure_propagates(self):
        self.failing = {'SetAVTransportURI'}
        with self.assertRaises(cast.CastError):
            cast.play(make_renderer(), Stream('http://h/v.mp4'))

    def test_uncastable_url_never_reaches_the_network(self):
        with self.assertRaises(cast.CastError):
            cast.play(make_renderer(), Stream('plugin://x/?action=play'))
        self.assertEqual(self.calls, [])

    def test_transport_controls(self):
        renderer = make_renderer()
        cast.pause(renderer)
        cast.resume(renderer)
        cast.stop(renderer)
        self.assertEqual(self._actions(), ['Pause', 'Play', 'Stop'])

    def test_transport_state_reported(self):
        self.responses['GetTransportInfo'] = {
            'CurrentTransportState': 'PLAYING'}
        self.assertEqual(cast.transport_state(make_renderer()), 'PLAYING')

    def test_transport_state_none_when_unreachable(self):
        self.failing = {'GetTransportInfo'}
        self.assertIsNone(cast.transport_state(make_renderer()))


class RendererServiceTypeTests(unittest.TestCase):
    def test_service_type_captured_from_description(self):
        r = dlna.parse_device_description(RENDERER_XML, 'http://h/d.xml')
        self.assertEqual(r.service_type,
                         'urn:schemas-upnp-org:service:AVTransport:1')

    def test_service_type_survives_the_scan_cache(self):
        r = make_renderer()
        self.assertEqual(Renderer.from_dict(r.to_dict()).service_type,
                         'urn:schemas-upnp-org:service:AVTransport:2')

    def test_defaults_when_a_cached_entry_predates_the_field(self):
        r = Renderer.from_dict({'udn': 'u', 'name': 'Old TV'})
        self.assertEqual(r.service_type,
                         'urn:schemas-upnp-org:service:AVTransport:1')


class RouterArgTests(unittest.TestCase):
    def _make_router(self, query):
        import sys
        if 'requests' not in sys.modules:
            sys.modules['requests'] = type(sys)('requests')
        from resources.lib import router as r
        return r.Router(['', '0', query])

    def test_int_arg_returns_int(self):
        r = self._make_router('?page=3')
        self.assertEqual(r._int_arg('page', 1), 3)

    def test_int_arg_default_on_missing(self):
        r = self._make_router('')
        self.assertEqual(r._int_arg('page', 1), 1)

    def test_int_arg_default_on_bad_input(self):
        r = self._make_router('?page=abc')
        self.assertEqual(r._int_arg('page', 1), 1)

    def test_int_arg_zero_default(self):
        r = self._make_router('?page=abc')
        self.assertEqual(r._int_arg('page'), 0)

    def test_switch_source_lists_sources_without_crashing(self):
        # Regression: action_switch_source used to shadow the `sources`
        # module with a local of the same name, raising UnboundLocalError
        # before the selection dialog could even open.
        sources.clear()
        sources.add_source('Source A', 'http://a/api')
        r = self._make_router('')
        original_select = kodiutils.select
        kodiutils.select = lambda heading, options: -1  # simulate cancel
        try:
            r.action_switch_source()  # must not raise
        finally:
            kodiutils.select = original_select


class StreamSubtitleTests(unittest.TestCase):
    def test_subtitle_optional(self):
        s = Stream('http://x/v.mp4')
        self.assertIsNone(s.subtitle)

    def test_subtitle_stored(self):
        s = Stream('http://x/v.mp4', subtitle='http://x/sub.en.vtt')
        self.assertEqual(s.subtitle, 'http://x/sub.en.vtt')

    def test_subtitle_roundtrip(self):
        s = Stream('http://x/v.mp4', subtitle='http://x/sub.en.vtt')
        d = s.to_dict()
        self.assertIn('subtitle', d)
        self.assertEqual(Stream.from_dict(d).subtitle,
                         'http://x/sub.en.vtt')

    def test_multiple_subtitles_default_empty(self):
        s = Stream('http://x/v.mp4')
        self.assertEqual(s.subtitles, [])
        self.assertEqual(s.all_subtitle_urls, [])

    def test_all_subtitle_urls_from_multiple_plain_strings(self):
        s = Stream('http://x/v.mp4',
                   subtitles=['http://x/sub.en.vtt', 'http://x/sub.fr.vtt'])
        self.assertEqual(s.all_subtitle_urls,
                         ['http://x/sub.en.vtt', 'http://x/sub.fr.vtt'])

    def test_all_subtitle_urls_from_dicts_with_language(self):
        s = Stream('http://x/v.mp4', subtitles=[
            {'url': 'http://x/sub.en.vtt', 'language': 'en'},
            {'url': 'http://x/sub.fr.vtt', 'language': 'fr'},
        ])
        self.assertEqual(s.all_subtitle_urls,
                         ['http://x/sub.en.vtt', 'http://x/sub.fr.vtt'])

    def test_all_subtitle_urls_merges_legacy_single_subtitle(self):
        s = Stream('http://x/v.mp4', subtitle='http://x/sub.es.vtt',
                   subtitles=['http://x/sub.en.vtt'])
        self.assertEqual(s.all_subtitle_urls,
                         ['http://x/sub.en.vtt', 'http://x/sub.es.vtt'])

    def test_multiple_subtitles_roundtrip(self):
        s = Stream('http://x/v.mp4', subtitles=[
            {'url': 'http://x/sub.en.vtt', 'language': 'en'},
        ])
        d = s.to_dict()
        self.assertEqual(d['subtitles'],
                         [{'url': 'http://x/sub.en.vtt', 'language': 'en'}])
        restored = Stream.from_dict(d)
        self.assertEqual(restored.all_subtitle_urls, ['http://x/sub.en.vtt'])


class _FakePlayItem(object):
    """Minimal ListItem stand-in covering what _apply_stream calls."""

    def __init__(self):
        self.calls = {}

    def setPath(self, v):
        self.calls['path'] = v

    def setProperty(self, k, v):
        self.calls.setdefault('properties', {})[k] = v

    def setMimeType(self, v):
        self.calls['mime_type'] = v

    def setContentLookup(self, v):
        self.calls['content_lookup'] = v

    def setSubtitles(self, urls):
        self.calls['subtitles'] = list(urls)


class ApplyStreamSubtitleTests(unittest.TestCase):
    """router._apply_stream must hand every subtitle URL to setSubtitles."""

    def _make_router(self):
        import sys
        if 'requests' not in sys.modules:
            sys.modules['requests'] = type(sys)('requests')
        from resources.lib import router as r
        return r.Router(['', '0', ''])

    def test_single_subtitle_is_passed(self):
        router = self._make_router()
        item = _FakePlayItem()
        stream = Stream('http://x/v.mp4', subtitle='http://x/sub.en.vtt')
        router._apply_stream(item, stream)
        self.assertEqual(item.calls.get('subtitles'), ['http://x/sub.en.vtt'])

    def test_multiple_subtitles_are_all_passed(self):
        router = self._make_router()
        item = _FakePlayItem()
        stream = Stream('http://x/v.mp4', subtitles=[
            'http://x/sub.en.vtt', 'http://x/sub.fr.vtt'])
        router._apply_stream(item, stream)
        self.assertEqual(item.calls.get('subtitles'),
                         ['http://x/sub.en.vtt', 'http://x/sub.fr.vtt'])

    def test_no_subtitles_means_no_call(self):
        router = self._make_router()
        item = _FakePlayItem()
        stream = Stream('http://x/v.mp4')
        router._apply_stream(item, stream)
        self.assertNotIn('subtitles', item.calls)


class SourceTests(unittest.TestCase):
    def setUp(self):
        sources.clear()
        kodiutils.set_setting('trakt_enabled', 'false')

    def test_default_source(self):
        src = sources.active_source()
        self.assertEqual(src['id'], 'default')
        self.assertEqual(src['name'], 'Content Source')

    def test_switch_source(self):
        sources.add_source('Source A', 'http://a/api')
        sources.add_source('Source B', 'http://b/api')
        sources.set_active('source1')
        self.assertEqual(sources.active_source()['name'], 'Source A')

    def test_active_url(self):
        sources.add_source('My Source', 'http://my/api')
        self.assertEqual(sources.active_url(), 'http://my/api')

    def test_remove_source_switches_active(self):
        sources.add_source('A', 'http://a')
        sources.add_source('B', 'http://b')
        sources.set_active('source1')
        sources.remove_source('source1')
        self.assertEqual(sources.active_source()['id'], 'default')

    def test_rename_source_persists(self):
        # Regression: rename_source used to mutate an in-memory dict from
        # one _load() call, then save a second, still-unmodified _load() --
        # a rename that silently never persisted.
        sid = sources.add_source('Original', 'http://x')
        sources.rename_source(sid, 'Renamed')
        self.assertEqual(sources.active_source()['name'], 'Renamed')
        # And it survives a fresh read from storage, not just the same process.
        self.assertEqual(
            [s['name'] for s in sources.all_sources() if s['id'] == sid],
            ['Renamed'])

    def test_rename_source_only_touches_the_matching_id(self):
        a = sources.add_source('A', 'http://a')
        b = sources.add_source('B', 'http://b')
        sources.rename_source(a, 'A renamed')
        names = {s['id']: s['name'] for s in sources.all_sources()}
        self.assertEqual(names[a], 'A renamed')
        self.assertEqual(names[b], 'B')

    def test_set_static_toggles_the_flag(self):
        sid = sources.add_source('S', 'http://s', static=False)
        sources.set_static(sid, True)
        self.assertTrue(sources.active_is_static())
        sources.set_static(sid, False)
        self.assertFalse(sources.active_is_static())

    def test_add_source_defaults_to_not_static(self):
        sources.add_source('S', 'http://s')
        self.assertFalse(sources.active_is_static())


class ManageSourcesRouterTests(unittest.TestCase):
    """The Manage sources screen: add/rename/toggle/remove/switch from the
    add-on's own menu, not just via tests of the sources.py module."""

    def _make_router(self, query=''):
        import sys
        if 'requests' not in sys.modules:
            sys.modules['requests'] = type(sys)('requests')
        from resources.lib import router as r
        return r.Router(['', '0', query])

    def setUp(self):
        sources.clear()
        import xbmcplugin
        xbmcplugin.added_items = []
        self.notified = []
        self.refreshed = []
        for name, replacement in (
            ('notify', lambda msg, *a, **k: self.notified.append(msg)),
            ('refresh_container', lambda: self.refreshed.append(True)),
            ('keyboard', lambda heading, default='': None),
            ('yesno_dialog', lambda *a, **k: False),
            ('ok_dialog', lambda msg, *a, **k: None),
        ):
            self.addCleanup(setattr, kodiutils, name, getattr(kodiutils, name))
            setattr(kodiutils, name, replacement)

    def test_manage_sources_lists_every_source_plus_add_entry(self):
        sources.add_source('Extra', 'http://extra')
        router = self._make_router()
        router.action_manage_sources()
        import xbmcplugin
        labels = [item['item'].label for item in xbmcplugin.added_items]
        # default + Extra + "Add new source"
        self.assertEqual(len(labels), 3)
        self.assertTrue(any('Extra' in lbl for lbl in labels))

    def test_manage_sources_marks_the_active_one(self):
        sid = sources.add_source('Extra', 'http://extra')
        sources.set_active(sid)
        router = self._make_router()
        router.action_manage_sources()
        import xbmcplugin
        active_labels = [item['item'].label for item in xbmcplugin.added_items
                        if item['item'].label.endswith('*')]
        self.assertEqual(len(active_labels), 1)
        self.assertIn('Extra', active_labels[0])

    def test_add_source_via_router(self):
        router = self._make_router()
        answers = iter(['My Source', 'http://my/api'])
        kodiutils.keyboard = lambda heading, default='': next(answers)
        kodiutils.yesno_dialog = lambda *a, **k: True
        router.action_add_source()
        names = [s['name'] for s in sources.all_sources()]
        self.assertIn('My Source', names)
        added = [s for s in sources.all_sources() if s['name'] == 'My Source'][0]
        self.assertTrue(added['static'])
        self.assertTrue(self.notified)
        self.assertTrue(self.refreshed)

    def test_add_source_cancelled_name_adds_nothing(self):
        router = self._make_router()
        before = len(sources.all_sources())
        kodiutils.keyboard = lambda heading, default='': None
        router.action_add_source()
        self.assertEqual(len(sources.all_sources()), before)

    def test_rename_source_via_router(self):
        sid = sources.add_source('Old Name', 'http://x')
        router = self._make_router('?source_id={0}'.format(sid))
        kodiutils.keyboard = lambda heading, default='': 'New Name'
        router.action_rename_source()
        self.assertEqual(
            [s['name'] for s in sources.all_sources() if s['id'] == sid],
            ['New Name'])

    def test_toggle_source_static_via_router(self):
        sid = sources.add_source('S', 'http://x', static=False)
        router = self._make_router('?source_id={0}'.format(sid))
        router.action_toggle_source_static()
        self.assertTrue(
            [s for s in sources.all_sources() if s['id'] == sid][0]['static'])
        router.action_toggle_source_static()
        self.assertFalse(
            [s for s in sources.all_sources() if s['id'] == sid][0]['static'])

    def test_remove_source_via_router_when_confirmed(self):
        sid = sources.add_source('S', 'http://x')
        router = self._make_router('?source_id={0}'.format(sid))
        kodiutils.yesno_dialog = lambda *a, **k: True
        router.action_remove_source()
        self.assertNotIn(sid, [s['id'] for s in sources.all_sources()])

    def test_remove_source_via_router_when_declined(self):
        sid = sources.add_source('S', 'http://x')
        router = self._make_router('?source_id={0}'.format(sid))
        kodiutils.yesno_dialog = lambda *a, **k: False
        router.action_remove_source()
        self.assertIn(sid, [s['id'] for s in sources.all_sources()])

    def test_switch_to_source_via_router(self):
        sid = sources.add_source('S', 'http://x')
        router = self._make_router('?source_id={0}'.format(sid))
        router.action_switch_to_source()
        self.assertEqual(sources.active_source()['id'], sid)
        self.assertTrue(self.notified)

    def test_test_connection_works_against_a_static_source(self):
        # action_test_connection ("Test connection" in Settings) needs no
        # static-specific branch: ContentSource.categories() already
        # dispatches on self.static, so this just needs to not blow up and
        # to report the right count.
        sources.add_source('Static', 'http://static.example', static=True)
        router = self._make_router()
        router.source._request = lambda url: {'categories': [
            {'id': 'a', 'name': 'A'}, {'id': 'b', 'name': 'B'}]}
        dialogs = []
        kodiutils.ok_dialog = lambda msg, *a, **k: dialogs.append(msg)
        router.action_test_connection()
        self.assertEqual(len(dialogs), 1)
        self.assertNotIn('str32043', dialogs[0])  # not the error-path string


class ContentSourceBaseUrlTests(unittest.TestCase):
    """The Settings -> Base API URL field must actually reach requests.

    Regression: ContentSource only ever read sources.active_url() (the
    multi-source manager's JSON store, always '' by default), so the
    single `base_url` setting that Settings exposes had no effect and
    every action silently failed with "configure a content source".
    """
    def setUp(self):
        sources.clear()
        kodiutils.set_setting('base_url', '')

    def tearDown(self):
        kodiutils.set_setting('base_url', '')

    def test_falls_back_to_base_url_setting_when_no_source_added(self):
        kodiutils.set_setting('base_url', 'http://legacy/api')
        self.assertEqual(content.ContentSource().base_url, 'http://legacy/api')

    def test_added_source_takes_priority_over_setting(self):
        kodiutils.set_setting('base_url', 'http://legacy/api')
        sources.add_source('Named Source', 'http://named/api')
        self.assertEqual(content.ContentSource().base_url, 'http://named/api')

    def test_empty_when_neither_is_configured(self):
        self.assertEqual(content.ContentSource().base_url, '')


class StaticSourceTests(unittest.TestCase):
    """The "static (no server)" mode: requests must be fixed file paths,
    with no query string, so a plain file host like GitHub Pages can serve
    them (see tools/build_static_demo.py)."""

    def setUp(self):
        sources.clear()
        cache.clear()  # cacheable _get_static() results share a global cache
        sources.add_source('Static Demo', 'http://static.example/demo', static=True)
        self.requested = []
        self.responses = {}
        self.source = content.ContentSource()
        self.source._request = self._fake_request

    def _fake_request(self, url):
        self.requested.append(url)
        return self.responses[url]

    def test_categories_hits_fixed_json_path(self):
        self.responses['http://static.example/demo/categories.json'] = \
            {'categories': [{'id': 'featured', 'name': 'Featured'}]}
        cats = self.source.categories()
        self.assertEqual(self.requested,
                         ['http://static.example/demo/categories.json'])
        self.assertEqual(cats[0].id, 'featured')

    def test_list_bakes_category_and_page_into_the_path(self):
        url = 'http://static.example/demo/list/featured/2.json'
        self.responses[url] = {'videos': [], 'page': 2, 'has_next': False}
        self.source.list_videos('featured', page=2)
        self.assertEqual(self.requested, [url])

    def test_resolve_bakes_video_id_into_the_path(self):
        url = 'http://static.example/demo/resolve/bbb.json'
        self.responses[url] = {'stream': 'http://x/bbb.mp4'}
        streams = self.source.resolve('bbb')
        self.assertEqual(self.requested, [url])
        self.assertEqual(streams[0].url, 'http://x/bbb.mp4')

    def test_search_degrades_to_empty_when_no_index_is_published(self):
        # No response registered for search-index.json -> the fake raises
        # KeyError; content.py must turn any ContentError from a missing
        # file into an empty result, not propagate an error.
        self.source._request = self._raise_content_error
        result = self.source.search('bunny')
        self.assertEqual(result.items, [])
        self.assertFalse(result.has_next)

    def _raise_content_error(self, url):
        self.requested.append(url)
        raise content.ContentError('404')

    def test_search_matches_title_case_insensitively(self):
        url = 'http://static.example/demo/search-index.json'
        self.responses[url] = {'videos': [
            {'id': 'bbb', 'title': 'Big Buck Bunny', 'url': 'http://x/bbb.mp4'},
            {'id': 'sintel', 'title': 'Sintel', 'url': 'http://x/sintel.mkv'},
        ]}
        result = self.source.search('BUNNY')
        self.assertEqual([v.id for v in result.items], ['bbb'])
        self.assertFalse(result.has_next)

    def test_search_fetches_index_only_once_across_calls(self):
        url = 'http://static.example/demo/search-index.json'
        self.responses[url] = {'videos': [
            {'id': 'bbb', 'title': 'Big Buck Bunny', 'url': 'http://x/bbb.mp4'},
        ]}
        self.source.search('bunny')
        self.source.search('bunny')
        self.assertEqual(self.requested, [url])  # second call was cached

    def test_search_paginates_using_page_size(self):
        url = 'http://static.example/demo/search-index.json'
        self.responses[url] = {'videos': [
            {'id': 'v{0}'.format(i), 'title': 'Match {0}'.format(i),
             'url': 'http://x/{0}.mp4'.format(i)} for i in range(5)
        ]}
        self.source.page_size = 2
        page1 = self.source.search('match', page=1)
        self.assertEqual([v.id for v in page1.items], ['v0', 'v1'])
        self.assertTrue(page1.has_next)
        page3 = self.source.search('match', page=3)
        self.assertEqual([v.id for v in page3.items], ['v4'])
        self.assertFalse(page3.has_next)

    def test_ids_with_special_characters_are_url_escaped(self):
        url = 'http://static.example/demo/list/kids%20%26%20family/1.json'
        self.responses[url] = {'videos': [], 'page': 1, 'has_next': False}
        self.source.list_videos('kids & family', page=1)
        self.assertEqual(self.requested, [url])


class TraktTests(unittest.TestCase):
    def setUp(self):
        sources.clear()
        kodiutils.set_setting('trakt_enabled', 'false')

    def test_disabled_by_default(self):
        self.assertFalse(trakt.enabled())

    def test_no_scrobble_when_disabled(self):
        v = Video(vid='v1', title='Test', trakt_id='123',
                  trakt_type='movie')
        trakt.scrobble_start(v)
        trakt.scrobble_stop(v, 30)
        trakt.scrobble_complete(v)

    def test_no_scrobble_without_trakt_id(self):
        kodiutils.set_setting('trakt_enabled', 'true')
        v = Video(vid='v1', title='Test')
        trakt.scrobble_start(v)
        trakt.scrobble_stop(v, 30)
        trakt.scrobble_complete(v)


if __name__ == '__main__':
    unittest.main()
