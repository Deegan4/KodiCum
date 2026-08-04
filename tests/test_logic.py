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

from resources.lib import (  # noqa: E402
    favorites, history, resume, kodiutils, cache, dlna, cast)
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


if __name__ == '__main__':
    unittest.main()
