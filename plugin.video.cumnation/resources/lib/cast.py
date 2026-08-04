# -*- coding: utf-8 -*-
"""Push a stream to a DLNA renderer and control it (UPnP AVTransport).

Casting over DLNA is not a media transfer -- nothing streams through Kodi.
``SetAVTransportURI`` hands the device a URL and some metadata, then ``Play``
tells it to start; the TV then fetches the video *itself*, directly from the
content source. Two consequences fall out of that and shape this module:

* The URL must be reachable **from the TV**, over plain HTTP(S). A local file
  path, a ``plugin://`` URL, or a host only Kodi can resolve will fail, so
  :func:`is_castable` rejects those before anything is sent.
* Playback continues on the TV whether or not Kodi is still running. Stopping
  it is an explicit action, which is why the transport controls exist here.

Commands are SOAP calls to the renderer's AVTransport control URL, discovered
by :mod:`dlna`. Argument *order* matters -- UPnP actions take positional
arguments despite the XML looking like a mapping -- so arguments are passed as
ordered pairs, never a dict.

:func:`soap_request` is the single network chokepoint; everything above it is
pure string handling and can be unit tested off-device.
"""
try:
    from urllib.parse import urlparse
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:  # pragma: no cover - Python 2 fallback
    from urlparse import urlparse
    from urllib2 import Request, urlopen, HTTPError, URLError

from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr

from . import kodiutils
from .dlna import local_name

SOAP_TIMEOUT = 10

#: DLNA playback flags advertised in ``protocolInfo``: seekable by byte range
#: (OP=01), no conversion (CI=0), plus the standard streaming flag set. TVs
#: that see no flags at all often refuse to seek, or refuse the item outright.
DLNA_FLAGS = ('DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS='
              '01700000000000000000000000000000')

ENVELOPE = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
    ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
    '<s:Body><u:{action} xmlns:u="{service}">{body}</u:{action}></s:Body>'
    '</s:Envelope>'
)

DIDL = (
    '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"'
    ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
    ' xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
    '<item id="0" parentID="-1" restricted="1">{body}</item>'
    '</DIDL-Lite>'
)

MIME_TYPES = {
    'mp4': 'video/mp4',
    'm4v': 'video/mp4',
    'mkv': 'video/x-matroska',
    'avi': 'video/x-msvideo',
    'mov': 'video/quicktime',
    'wmv': 'video/x-ms-wmv',
    'webm': 'video/webm',
    'ts': 'video/mpeg',
    'mpg': 'video/mpeg',
    'mpeg': 'video/mpeg',
    'flv': 'video/x-flv',
    'm3u8': 'application/vnd.apple.mpegurl',
    'mpd': 'application/dash+xml',
}
DEFAULT_MIME = 'video/mp4'

#: Transport states a renderer can report from GetTransportInfo.
PLAYING = 'PLAYING'
PAUSED = 'PAUSED_PLAYBACK'
STOPPED = 'STOPPED'


class CastError(Exception):
    """Raised when a renderer refuses or cannot be reached."""


# -- helpers --------------------------------------------------------------
def is_castable(url):
    """True if a URL is one a TV could fetch on its own.

    DLNA hands the device a URL to retrieve, so anything Kodi resolves
    internally -- ``plugin://``, ``file://``, a bare path -- is unusable no
    matter how well it plays locally.
    """
    if not url:
        return False
    return urlparse(url).scheme in ('http', 'https')


def guess_mime(url, fallback=DEFAULT_MIME):
    """Guess a MIME type from a URL's file extension."""
    path = urlparse(url or '').path
    _, _, extension = path.rpartition('.')
    return MIME_TYPES.get(extension.lower(), fallback)


def format_duration(seconds):
    """Format seconds as the ``H:MM:SS.mmm`` form UPnP expects."""
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return '{0}:{1:02d}:{2:02d}.000'.format(hours, minutes, secs)


def build_metadata(stream, video=None):
    """Build the DIDL-Lite document describing an item to a renderer.

    Sending metadata is technically optional, but a bare URI leaves the TV
    guessing: many refuse an item whose ``protocolInfo`` they never saw, and
    those that accept it show a blank title. Populating title, artwork and
    duration is what makes the item look right on screen.
    """
    mime = stream.mime_type or guess_mime(stream.url)
    protocol = 'http-get:*:{0}:{1}'.format(mime, DLNA_FLAGS)

    title = (video.title if video else None) or 'Video'
    parts = ['<dc:title>{0}</dc:title>'.format(escape(title)),
             '<upnp:class>object.item.videoItem</upnp:class>']
    if video is not None:
        if video.plot:
            parts.append('<dc:description>{0}</dc:description>'.format(
                escape(video.plot)))
        if video.thumb:
            thumb = escape(video.thumb)
            parts.append(
                '<upnp:albumArtURI>{0}</upnp:albumArtURI>'.format(thumb))
            parts.append('<upnp:icon>{0}</upnp:icon>'.format(thumb))

    attrs = ['protocolInfo={0}'.format(quoteattr(protocol))]
    duration = format_duration(video.duration if video else None)
    if duration:
        attrs.append('duration={0}'.format(quoteattr(duration)))
    parts.append('<res {0}>{1}</res>'.format(
        ' '.join(attrs), escape(stream.url)))

    return DIDL.format(body=''.join(parts))


def build_envelope(service_type, action, arguments):
    """Build a SOAP envelope. ``arguments`` is an ordered sequence of pairs."""
    body = ''.join(
        '<{0}>{1}</{0}>'.format(name, escape('' if value is None else str(value)))
        for name, value in arguments)
    return ENVELOPE.format(action=action, service=service_type, body=body)


def parse_response(xml_text):
    """Return the ``<u:...Response>`` child elements as a dict."""
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return {}
    for element in root.iter():
        if local_name(element.tag).endswith('Response'):
            return {local_name(child.tag): (child.text or '')
                    for child in element}
    return {}


def parse_fault(xml_text):
    """Extract a readable message from a UPnP SOAP fault, or None.

    A refusing renderer answers HTTP 500 with a ``UPnPError`` carrying a
    numeric code -- 701 "transition not available", 714 "illegal MIME type",
    716 "resource not found by the device". Surfacing the code matters: it is
    the difference between "your TV can't play this format" and "your TV
    couldn't download the URL", which need very different fixes.
    """
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return None
    code = description = None
    for element in root.iter():
        name = local_name(element.tag)
        if name == 'errorCode':
            code = (element.text or '').strip()
        elif name == 'errorDescription':
            description = (element.text or '').strip()
    if not code and not description:
        return None
    if code and description:
        return '{0} ({1})'.format(description, code)
    return description or code


# -- transport ------------------------------------------------------------
def soap_request(renderer, action, arguments=()):
    """Invoke an AVTransport action. Returns the response values as a dict.

    This is the only function here that touches the network; tests replace it
    to exercise the command layer.
    """
    if not renderer.control_url:
        raise CastError(kodiutils.get_string(32082))

    envelope = build_envelope(renderer.service_type, action, arguments)
    request = Request(renderer.control_url, data=envelope.encode('utf-8'))
    request.add_header('Content-Type', 'text/xml; charset="utf-8"')
    request.add_header('SOAPACTION', '"{0}#{1}"'.format(
        renderer.service_type, action))

    kodiutils.log('AVTransport {0} -> {1}'.format(action, renderer.control_url))
    try:
        handle = urlopen(request, timeout=SOAP_TIMEOUT)
        try:
            return parse_response(handle.read().decode('utf-8', 'replace'))
        finally:
            handle.close()
    except HTTPError as exc:
        message = None
        try:
            message = parse_fault(exc.read().decode('utf-8', 'replace'))
        except (OSError, ValueError):        # pragma: no cover - unreadable body
            pass
        kodiutils.log_error('{0} refused by {1}: {2}'.format(
            action, renderer.label, message or exc))
        raise CastError(message or str(exc))
    except (URLError, OSError, ValueError) as exc:
        kodiutils.log_error('{0} failed for {1}: {2}'.format(
            action, renderer.label, exc))
        raise CastError(str(exc))


def play(renderer, stream, video=None):
    """Hand a stream to a renderer and start it playing."""
    if not is_castable(stream.url):
        raise CastError(kodiutils.get_string(32081))

    # Stop first: a renderer mid-playback may reject SetAVTransportURI with a
    # 701 "transition not available", and a stray failure here is harmless.
    try:
        soap_request(renderer, 'Stop', (('InstanceID', 0),))
    except CastError:
        pass

    soap_request(renderer, 'SetAVTransportURI', (
        ('InstanceID', 0),
        ('CurrentURI', stream.url),
        ('CurrentURIMetaData', build_metadata(stream, video)),
    ))
    soap_request(renderer, 'Play', (('InstanceID', 0), ('Speed', 1)))


def stop(renderer):
    soap_request(renderer, 'Stop', (('InstanceID', 0),))


def pause(renderer):
    soap_request(renderer, 'Pause', (('InstanceID', 0),))


def resume(renderer):
    soap_request(renderer, 'Play', (('InstanceID', 0), ('Speed', 1)))


def transport_state(renderer):
    """Return the device's current transport state, or None if unreachable."""
    try:
        info = soap_request(renderer, 'GetTransportInfo',
                            (('InstanceID', 0),))
    except CastError:
        return None
    return info.get('CurrentTransportState') or None
